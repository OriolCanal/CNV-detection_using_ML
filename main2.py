import pyliftover
import os
import sys
import pandas as pd
import random
# from modules.create_mongo import MongoDBManager
# from modules.mongo_classes import Variant, Call, MongoDBManager, Annotation
# from modules.mongo_classes import Run as Mongo_Run
# from modules.mongo_classes import Sample as Mongo_Sample
from modules.bed import Bed
from modules.bam import Bam
from modules.detected_CNV import In_Silico_CNV, Detected_CNV
from modules.CNV_detection_algorithms.CNV_Kit import CNV_Kit
from modules.CNV_detection_algorithms.decon import Decon
from modules.CNV_detection_algorithms.gatk_gCNV import Gatk_gCNV, Case_Gatk_gCNV, Cohort_Gatk_gCNV
from modules.CNV_detection_algorithms.grapes import Grapes
from modules.params import load_config
from modules.log import logger
from modules.picard import Picard, Metrics_Df
from modules.mosdepth import Mosdepth, Mosdepth_df, Cohort_Mosdepth_df, Analysis_Mosdepth_df, Joined_Mosdepth_Df
from modules.clustering import Clustering_Mosdepth
from modules.run_class import Analysis_Run, Sample 
from modules.utils import get_timestamp
from modules.cnv_generator import CNV_Generator
logger.info(f"loading configuration files.")
ann_conf, ref_conf, docker_conf, isoforms_conf = load_config()


Bed_obj = Bed(ref_conf.bed)


Picard_Obj = Picard(docker_conf, ref_conf)
Picard_Obj.create_fasta_dict()
Picard_Obj.run_bed_to_interval_list(Bed_obj)


Mosdepth_Obj = Mosdepth(docker_conf)

Analysis_Picard_Metrics_Df = Metrics_Df()
Cohort_Picard_Metrics_Df = Metrics_Df()

Analysis_Mosdepth_Metrics_Df = Mosdepth_df(ref_conf)
Cohort_Mosdepth_Metrics_Df = Cohort_Mosdepth_df(ref_conf)

analysis_sample_id_sample_obj = dict()
cohort_sample_id_sample_obj = dict()

cohort_samples = set()
analysis_samples = set()
analysis_runs = set()

samples_analysed = set()
samples_analysed2 = dict()
# total_samples = 124
num_cohort_samples = 120
i = 0

analysis_runs = set()
cohort_runs = set()

# Set the random seed
random_seed = 42  # You can choose any integer value
random.seed(random_seed)
runs = os.listdir(ref_conf.bam_dir)
random.shuffle(runs)

# stores sample_id : sample_obj
sample_id_sample_obj = dict()
for run in runs:
    run_path = os.path.join(ref_conf.bam_dir, run)
    bams_bais = os.listdir(run_path)
    bams = [bam for bam in bams_bais if bam.endswith(".bam")]
    # runs with less than 4 samples can't be analysed by DECON, so we put in cohort
    if len(bams) < 4:
        cohort = True
        run_list = cohort_runs
    elif i + len(bams) > num_cohort_samples:
        cohort = False
        run_list = analysis_runs
    else:
        cohort = True
        run_list = cohort_runs

    Run = Analysis_Run(run_path, is_cohort=cohort)
    Run.get_Bams_and_Samples()

    run_list.add(Run)
    # if i + len(Run.samples_147) > num_cohort_samples:
    #     analyse_run.append(Run)
    for Sample_147 in Run.samples_147:
        i += 1

    
    run_list.add(Run)

# for run in cohort_runs:
#     run.put_bams_in_cohort_dir(ref_conf)
# for run in analysis_runs:
#     run.put_bams_in_analysis_dir(ref_conf)

# print(f"cohorts runs: {len(cohort_runs)}")

# generate in silico cnvs
CNV_generator = CNV_Generator(Bam.analysis_bam_dir, ref_conf, Bed_obj)
CNV_generator.create_multiple_exons_config(cnv_type="del", out_filename="multiple_exons_deletion.config")
CNV_generator.create_multiple_exons_config(cnv_type="dup", out_filename="multiple_exons_duplication.config")
CNV_generator.create_single_exons_config(cnv_type="del", out_filename="single_exon_deletion.config")
CNV_generator.create_single_exons_config(cnv_type="dup", out_filename="single_exon_duplication.config")
filtered_config = CNV_generator.check_config_overlap()
# print(filtered_config)
# CNVs_bams_dir = CNV_generator.generate_cnvs()
in_silico_cnvs = In_Silico_CNV.parse_cnvs_config(config_path=filtered_config, sample_id_sample_obj=Sample.sample_id_sample_obj)
CNV_generator.order_config(by_column=0)
CNV_generator.order_config(by_column=1)

CNVs_bams_dir = "/home/ocanal/Desktop/CNV_detection_on_targeted_sequencing/bams_with_cnvs"

for run in analysis_runs:

    for sample in run.samples_147:
        run_path = os.path.join(CNVs_bams_dir, run.run_id)
        if not os.path.exists(run_path):
            sample.bam.set_simulated_bam(CNVs_bams_dir) # Bam path is now the simulated path
        else:
            sample.bam.set_simulated_bam(run_path)
    run.put_bam_in_run_directory()

for Cohort_Run in cohort_runs:
    # Cohort_Run.put_bam_in_run_directory()
    for Cohort_Sample in Cohort_Run.samples_147:
        print(Cohort_Sample.bam.symbolic_link)
        cohort_sample_id_sample_obj[Cohort_Sample.sample_id] = Cohort_Sample
        cohort_samples.add(Cohort_Sample)
        # Picard
        Picard_Obj.run_collectHsMetrics(Cohort_Sample.bam, Bed_obj)
        info_line, value_line = Picard_Obj.get_picard_metrics(Cohort_Sample.bam)
        if not Cohort_Picard_Metrics_Df.has_df_header():
            Cohort_Picard_Metrics_Df.add_metrics_header(info_line)
        Cohort_Picard_Metrics_Df.add_metrics_line(value_line)
        # Mosdepth
        Mosdepth_Obj.run_mosdepth(Cohort_Sample.bam.path, force=False)
        exon_coverage, sample_mean_coverage = Mosdepth_Obj.parse_mosdepth_regions_bed()
        Cohort_Mosdepth_Metrics_Df.add_normalized_mean_coverage_dict(exon_coverage, sample_mean_coverage)

exons_mean_coverage_df = Cohort_Mosdepth_Metrics_Df.get_df_from_normalized_exons_coverage()
Cohort_Mosdepth_Metrics_Df.apply_pca(normalized=True)
Analysis_Mosdepth_Metrics_Df = Analysis_Mosdepth_df(ref_conf, Cohort_Mosdepth_Metrics_Df.scaler, Cohort_Mosdepth_Metrics_Df.pca)

# PCA
Cluster_Pca = Clustering_Mosdepth(Cohort_Mosdepth_Metrics_Df, "PCA", ref_conf)
Cluster_Pca.apply_hdbscan(min_samples=5, min_cluster_size=2)
Cluster_Pca.apply_dbscan(epsilon=25, min_pts=20, k_graph=True)
# Cluster_Pca.apply_bayesian_gaussian_mixture()
# Cluster_Pca.do_hierarchical_clustering()
cluster_samples = Cluster_Pca.set_hdbscan_cluster_samples(cohort_sample_id_sample_obj)

# UMAP
# Cluster_Umap = Clustering_Mosdepth(Mosdepth_Metrics_Df, "UMAP", ref_conf)
# Cluster_Umap.apply_bayesian_gaussian_mixture()
# Cluster_Umap.do_hierarchical_clustering()
# Cluster_Umap.apply_hdbscan(min_samples=15, min_cluster_size=3)
for Analysis_run in analysis_runs:
    # Analysis_run.create_symbolic_link(ref_conf)
    for Analysis_sample in Analysis_run.samples_147:
        analysis_sample_id_sample_obj[Analysis_sample.sample_id] = Analysis_sample
        analysis_samples.add(Analysis_sample)
        # Picard
        Picard_Obj.run_collectHsMetrics(Analysis_sample.bam, Bed_obj)
        info_line, value_line = Picard_Obj.get_picard_metrics(Analysis_sample.bam)
        if not Analysis_Picard_Metrics_Df.has_df_header():
            Analysis_Picard_Metrics_Df.add_metrics_header(info_line)
        Analysis_Picard_Metrics_Df.add_metrics_line(value_line)

        # Mosdepth
        Mosdepth_Obj.run_mosdepth(Analysis_sample.bam.path, force=False)
        exon_coverage, sample_mean_coverage = Mosdepth_Obj.parse_mosdepth_regions_bed()
        Analysis_Mosdepth_Metrics_Df.add_normalized_mean_coverage_dict(exon_coverage, sample_mean_coverage)

Analysis_Mosdepth_Metrics_Df.get_df_from_normalized_exons_coverage()
Analysis_Mosdepth_Metrics_Df.transform_to_pca_space()
Joined_Mosdepth_df = Joined_Mosdepth_Df(ref_conf, Cohort_Mosdepth_Metrics_Df.pca_df, Analysis_Mosdepth_Metrics_Df.pca_df)
joined_df = Joined_Mosdepth_df.joined_df
print(joined_df)
# Joined_Mosdepth_df.get_n_pca_closest_samples("RB36313")
Joined_Mosdepth_df.detect_outliers(z_score_threshold=2)
Joined_Mosdepth_df.assign_sample_outliers(analysis_sample_id_sample_obj, cohort_sample_id_sample_obj)


# removing outlier from cohort and analysis
cohort_samples = {sample for sample in cohort_samples if sample.is_outlier is False}
analysis_samples = {sample for sample in analysis_samples if sample.is_outlier is False}

for run in cohort_runs:
    run.put_bams_in_cohort_dir(ref_conf)
# for run in analysis_runs:
#     run.put_bams_in_analysis_dir(ref_conf)
# GRAPES

# for run in analysis_runs:


#     Grapes_obj = Grapes(docker_conf, ref_conf, run, Bed_obj)


#     Grapes_obj.get_grapes_bed()
#     are_samples_to_analyse = Grapes_obj.create_input_file()
#     # at least we need 2 samples to be analysed
#     if not are_samples_to_analyse:
#         continue
#     Grapes_obj.run_grapes_run_mode()
#     Grapes_obj.parse_dectected_cnvs(Bed_obj, Sample.sample_id_sample_obj)
# logger.info(
#     f"Total amount of CNVs detected by Grapes2 is: {len(Detected_CNV.cnvs["GRAPES2"])}"
# )

# GATK gCNV
# force_run = False
# Gatk_obj = Gatk_gCNV(docker_conf, ref_conf, Bed_obj, force_run)
# Gatk_obj.run_preprocess_intervals()
# # creating hdf5 file for each sample
# for cohort_Sample in cohort_samples:

#     Gatk_obj.run_collect_read_counts(cohort_Sample)

# Gatk_obj.run_index_feature_file()
# Gatk_obj.run_annotate_intervals()
# Gatk_obj.run_filter_intervals(cohort_samples)
# Gatk_obj.run_interval_list_tools()
# Gatk_Cohort = Cohort_Gatk_gCNV(docker_conf, ref_conf, Bed_obj, cohort_samples, force_run)
# Gatk_Cohort.run_determine_germline_contig_ploidy()
# Gatk_Cohort.run_germline_cnv_caller()


# CNV_KIT
CnvKit = CNV_Kit(docker_conf, ref_conf, Bed_obj)

CnvKit.run_batch_germline_pipeline(cohort_samples, analysis_samples)
CnvKit.parse_detected_cnvs(Bed_obj, Sample.sample_id_sample_obj)
print(Detected_CNV.cnvs)
num_cnvs_detected_cnvkit = len(Detected_CNV.cnvs["CNVKIT"])

logger.info(
    f"Total amount of CNVs detected by CNVKit is: {num_cnvs_detected_cnvkit}"
)
# for analysis_run in analysis_runs:
#     # runs with only 1 sample cannot be analysed
#     if not len(analysis_run.samples_147) > 3:
#         continue
#     # RUN DECON
#     Decon_obj = Decon(docker_conf, ref_conf, Bed_obj, analysis_run)
#     Decon_obj.get_input_file()
#     Decon_obj.run_read_in_bams()
#     Decon_obj.run_identify_failed_rois()
#     Decon_obj.run_make_CNVcalls()
#     # for Analysis_Sample in analysis_run.samples_147:
#         # RUN GATK
#         # Gatk_obj.run_collect_read_counts(Analysis_Sample)
#         # Sample_Case_Gatk_gCNV = Case_Gatk_gCNV(Gatk_Cohort, Analysis_Sample, docker_conf, ref_conf, Bed_obj, force_run)
#         # Sample_Case_Gatk_gCNV.run_determine_germline_contig_ploidy()
#         # Sample_Case_Gatk_gCNV.run_germline_cnv_caller()
#         # Sample_Case_Gatk_gCNV.run_postprocess_germline_calls()
#         # Sample_Case_Gatk_gCNV.process_detected_cnvs()

# Decon_obj.parse_DECON_result(Sample.sample_id_sample_obj)
# print(len(Detected_CNV.cnvs["DECON"]), "heeey")
# # creating a model for each sample
# for cluster in cluster_samples.keys():
#     # Skipping outliers
#     if cluster == -1:
#         continue
#     cohort_samples = cluster_samples[cluster]
#     print(cohort_samples)
#     bams = list()
#     for sample in cohort_samples:
#         # Gatk_obj.run_filter_intervals(sample, cohort_samples)
#         Sample_Case_Gatk_gCNV = Case_Gatk_gCNV(sample, docker_conf, ref_conf, Bed_obj, force_run)
#         Sample_Case_Gatk_gCNV.run_determine_germline_contig_ploidy(Gatk_Cohort)
#         Sample_Case_Gatk_gCNV.run_germline_cnv_caller(Gatk_Cohort)
#         Sample_Case_Gatk_gCNV.run_postprocess_germline_calls(Gatk_Cohort)
#         bams.append(sample.bam.path)
#     print(f"bams of cluster {cluster}:\n {bams}")

# mosdepth_excel_path = os.path.join(ref_conf.main_dir, "mosdepth_excel.xlsx")
# exons_mean_coverage_df = Mosdepth_Metrics_Df.get_df_from_normalized_exons_coverage()
# logger.info(f"Creating mosdepth coverage dataframe in {mosdepth_excel_path}")
# exons_mean_coverage_df.to_excel(mosdepth_excel_path, index=False)

# # heatmap_path = os.path.join(ref_conf.main_dir, "Mosdepth_heatmap.png")
# Mosdepth_Metrics_Df.apply_pca(normalized=True)
# # closes_points = Mosdepth_Metrics_Df.get_n_pca_closest_samples("RB36157", n=5)
# Mosdepth_Metrics_Df.apply_umap(normalized=True)
# Cluster_Pca = Clustering_Mosdepth(Mosdepth_Metrics_Df, "PCA", ref_conf)
# # Cluster_Pca.apply_bayesian_gaussian_mixture()
# # Cluster_Pca.do_hierarchical_clustering()
# Cluster_Pca.apply_hdbscan(min_samples=15, min_cluster_size=5)

# Cluster_Umap = Clustering_Mosdepth(Mosdepth_Metrics_Df, "UMAP", ref_conf)
# # Cluster_Umap.apply_bayesian_gaussian_mixture()
# # Cluster_Umap.do_hierarchical_clustering()
# Cluster_Umap.apply_hdbscan(min_samples=15, min_cluster_size=3)

# cluster_samples = Cluster_Pca.get_hdbscan_cluster_samples(analysis_samples)

# # if force_run = True, if output file of gatk exists, the command will run and the file will be overwritten
# force_run = False
# # # Run GATK gCNV
# Picard_Obj.run_bed_to_interval_list(Bed_obj)
# Gatk_obj = Gatk_gCNV(docker_conf, ref_conf, Bed_obj, force_run)
# Gatk_obj.run_preprocess_intervals()
# Gatk_obj.run_index_feature_file()
# Gatk_obj.run_annotate_intervals()

# # creating hdf5 file for each sample
# for sample in analysis_samples.values():

#     Bam_Obj = sample.bam
#     Gatk_obj.run_collect_read_counts(Bam_Obj)

# # creating a model for each sample
# for cluster in cluster_samples.keys():
#     if cluster == -1:
#         continue
#     cohort_samples = cluster_samples[cluster]
#     print(cohort_samples)
#     bams = list()
#     for sample in cohort_samples:
#         Gatk_obj.run_filter_intervals(sample, cohort_samples)
#         Gatk_obj.run_interval_list_tools()
#         Gatk_obj.run_filter_intervals(sample, cohort_samples)
#         Gatk_Cohort = Cohort_Gatk_gCNV(sample, docker_conf, ref_conf, Bed_obj, cohort_samples, force_run)
#         Sample_Case_Gatk_gCNV = Case_Gatk_gCNV(sample, docker_conf, ref_conf, Bed_obj, force_run)
#         Gatk_Cohort.run_determine_germline_contig_ploidy(sample)
#         Sample_Case_Gatk_gCNV.run_determine_germline_contig_ploidy(Gatk_Cohort)
#         Gatk_Cohort.run_germline_cnv_caller(sample)
#         Sample_Case_Gatk_gCNV.run_germline_cnv_caller(Gatk_Cohort)
#         Sample_Case_Gatk_gCNV.run_postprocess_germline_calls(Gatk_Cohort)
#         bams.append(sample.bam.path)
#     print(f"bams of cluster {cluster}:\n {bams}")