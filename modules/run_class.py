# USED WHEN BAMS WERE IMPORTED FROM THE DB
import os
import subprocess
import shutil

from modules.log import logger
from modules.mongo_classes import Sample
from modules.bam import Bam
class Analysis_Run():
    samples_analysed = set()
    duplicated_samples = set()
    def __init__(self, run_path, is_cohort=False):
        self.run_path = run_path
        self.run_id = os.path.basename(run_path)
        self.samples_147 = list()
        self.is_cohort = is_cohort
    
    def create_symbolic_link(self, ref_conf):
        if self.is_cohort:
            self.symbolic_link_dir = os.path.join(ref_conf.main_dir, "cohort_symbolic_link")
            if not os.path.exists(self.symbolic_link_dir):
                os.mkdir(self.symbolic_link_dir)
        if not self.is_cohort:
            self.symbolic_link_dir = os.path.join(ref_conf.main_dir, "analysis_symbolic_link")
            if not os.path.exists(self.symbolic_link_dir):
                os.mkdir(self.symbolic_link_dir)
        
        for sample in self.samples_147:
            


            destination_bam_path = os.path.join(self.symbolic_link_dir, sample.bam.filename)
            destination_bai_path = os.path.join(self.symbolic_link_dir, sample.bam.bai_filename)
            if not os.path.exists(destination_bam_path):
                os.symlink(sample.bam.path, destination_bam_path)
                os.symlink(sample.bam.bai_path, destination_bai_path)

                bam = sample.bam
                bam.set_symbolic_link(destination_bam_path)

    # def get_samples_from_db(self, Run_mongo):
    #     try:
    #         run_doc = Run_mongo.objects.get(run_id=self.run_id)
    #     except:
    #         logger.warning(
    #             f"Run ID: {self.run_id} not found in MongoDb!"
    #         )
        
    #     if hasattr(run_doc, "samples"):
    #         samples = run_doc.samples
    #         for sample_id in samples:
    #             Sample = Analysis_Sample(run_id=self.run_id, sample_id=sample_id)
    #             self.samples_ids.append(Sample)
    #             if Sample.is_panel_147(Sample_mongo):
    #                 self.samples_147.append(Sample)

    #     else:
    #         raise (ValueError(
    #             f"Run ID: {self.run_id} does not contain any sample"
    #         ))

    def remove_sample(self, Sample):
        if Sample in self.samples_147:
            self.samples_147.remove(Sample)
        else:
            raise ValueError(
                f" Sample: {Sample.sample_id} not in run {self.run_id}"
            )


    def get_Bams_and_Samples(self):
        bams_bais = os.listdir(self.run_path)
        bams = [bam for bam in bams_bais if bam.endswith(".bam")]

        for bam in bams:
            # avoiding duplicated samples
            if bam not in self.samples_analysed:
                self.samples_analysed.add(bam)
            else:
                logger.info(
                    f"Bam: {bam} already analysed"
                )
                continue
                
            bam_path = os.path.join(self.run_path, bam)
            self.duplicated_samples.add(bam_path)
            Bam_class = Bam(bam_path)
            sample_name = bam.split(".")[0]
            sample = Sample(Bam=Bam_class, sample_id=sample_name, run_id=self.run_id, is_cohort=self.is_cohort)
            self.samples_147.append(sample)

class Sample():
    compendi_bai_path = "http://172.16.83.24:8001/download_sample_bai/"
    compendi_bam_path = "http://172.16.83.24:8001/download_sample_bam/"

    def __init__(self, Bam, sample_id=None, run_id=None, is_cohort=False):
        self.run_id = run_id
        self.sample_id = sample_id
        self.downloaded_bam = False
        self.bam = Bam # Bam class containing info about bam files
        self.cluster = None
        self.is_outlier = False
        self.is_cohort = is_cohort


class Analysis_Sample():
    compendi_bai_path = "http://172.16.83.24:8001/download_sample_bai/"
    compendi_bam_path = "http://172.16.83.24:8001/download_sample_bam/"

    def __init__(self, Bam, sample_id=None, run_id=None):
        self.run_id = run_id
        self.sample_id = sample_id
        self.downloaded_bam = False
        self.bam = Bam # Bam class containing info about bam files
        self.assigned_cluster = None
        self.is_outlier = False


# class Analysis_Sample():
#     compendi_bai_path = "http://172.16.83.24:8001/download_sample_bai/"
#     compendi_bam_path = "http://172.16.83.24:8001/download_sample_bam/"

#     def __init__(self, sample_id, Bam=None, run_id=None):
#         self.run_id = run_id
#         self.sample_id = sample_id
#         self.downloaded_bam = False
#         self.bam = Bam # Bam class containing info about bam files
#         self.cluster = None
#     def is_panel_147(self, Sample_mongo):
#         try:
#             sample_doc = Sample_mongo.objects.get(run_id=self.run_id, lab_id=self.sample_id)
#         except:
#             logger.warning(
#                 f"Sample ID: {self.sample_id} not found in MongoDb Sample collection!"
#             )
#             return False
        
#         if hasattr(sample_doc, "panel"):
#             if "SUDD_147" in sample_doc.panel:
#                 self.panel_147 = True
#                 return(True)
#             elif sample_doc.panel == "147":
#                 self.panel_147 = True
#                 return(True)
#             self.panel_147 = False
#             return False
        
#         raise ValueError(
#             f"Sample document with ID {self.sample_id} does not contain a panel attribute!"
#         )
    
            
#     def get_bam_bai_from_compendi(self, ref_conf):
#         if not self.panel_147:
#             logger.warning(f"Bam file won't be downloaded as it's not panel SUDD_147")
#             return(0)
#         output_dir = os.path.join(ref_conf.main_dir, "runs")

#         if not os.path.isdir(output_dir):
#             logger.info(f"Creating directory {output_dir} to store bam bai files.")
#             os.mkdir(output_dir)

#         run_dir = os.path.join(output_dir, self.run_id)
#         if not os.path.isdir(run_dir):
#             os.mkdir(run_dir)
#         sample_bam = f"{self.sample_id}.bam"
#         sample_bai = f"{self.sample_id}.bai"
#         bam_path = os.path.join(run_dir, sample_bam)
#         bai_path = os.path.join(run_dir, sample_bai)
#         if not os.path.isfile(bam_path):
#             download_bam_compendi = os.path.join(Analysis_Sample.compendi_bam_path, self.sample_id, self.run_id)

#             result = subprocess.run(["wget", "-O", bam_path, download_bam_compendi])

#             if result.returncode == 0:
#                 logger.info(f"{bam_path} downloaded successfully!")
#                 self.bam = Bam(bam_path)
#             else:
#                 logger.error(
#                     f"Download from {download_bam_compendi} failed with return code: {result.returncode}"
#                 )
#                 if os.path.isfile(bam_path):
#                     shutil.rmtree(run_dir)
#                 return(False)
#         else:
#             self.bam = Bam(bam_path)
#             logger.info(
#                 f"Bam file: {bam_path} has previously been downloaded!"
#             )

#         if not os.path.isfile(bai_path):
#             download_bai_compendi = os.path.join(Analysis_Sample.compendi_bai_path, self.sample_id, self.run_id)

#             result_bairef_config.bam_dir) = subprocess.run(["wget", "-O", bai_path, download_bai_compendi])

#             if result_bai.returncode == 0:
#                 logger.info(f"{bai_path} downloaded successfully!")
#                 self.bam = Bam(bam_path)
#             else:
#                 logger.error(
#                     f"Download from {download_bai_compendi} failed with return code: {result.returncode}"
#                 )
#                 if os.path.isfile(bai_path):
#                     shutil.rmtree(run_dir)
#                 return(False)
#         else:
#             logger.info(
#                 f"Bai file: {bai_path} has previously been downloaded!"
#             )

#         return(self.bam)
        
