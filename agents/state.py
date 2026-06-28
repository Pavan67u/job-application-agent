from typing import TypedDict, List, Optional, Annotated
from pydantic import BaseModel
import operator


class JobListing(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str  # linkedin | naukri | indeed
    description: str
    posted_date: str
    experience_required: str = ""
    skills_required: List[str] = []
    match_score: float = 0.0
    applied: bool = False
    application_status: str = "pending"  # pending | applied | failed | skipped
    resume_version: str = ""
    error_msg: str = ""


class AgentState(TypedDict):
    # Input
    job_titles: List[str]
    location: str
    base_resume_path: str

    # Scraped jobs
    raw_jobs: Annotated[List[JobListing], operator.add]

    # After scoring
    scored_jobs: List[JobListing]

    # After resume rewriting
    tailored_jobs: List[JobListing]

    # After applying
    applied_jobs: Annotated[List[JobListing], operator.add]
    failed_jobs: Annotated[List[JobListing], operator.add]

    # Final
    tracker_path: str
    run_summary: dict
