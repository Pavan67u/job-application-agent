from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")

JOB_TITLES = os.getenv("JOB_TITLES", "Software Engineer,Data Analyst").split(",")
JOB_LOCATION = os.getenv("JOB_LOCATION", "Hyderabad")
EXPERIENCE_YEARS = int(os.getenv("EXPERIENCE_YEARS", "0"))
MAX_JOBS_PER_RUN = int(os.getenv("MAX_JOBS_PER_RUN", "20"))

BASE_RESUME_PATH = os.getenv("BASE_RESUME_PATH", "data/resumes/base_resume.docx")
TRACKER_PATH = os.getenv("TRACKER_PATH", "data/output/job_tracker.xlsx")
RUN_INTERVAL_HOURS = int(os.getenv("RUN_INTERVAL_HOURS", "12"))
