from google import genai
import json
import re
from agents.state import JobListing
from config.settings import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.0-flash"


from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True
)
def parse_jd_and_score(job: JobListing, base_resume_text: str) -> tuple[JobListing, dict]:
    """Extract skills from JD and score match against resume."""
    prompt = f"""
You are a job application assistant. Analyze this job description and candidate resume.

JOB TITLE: {job.title}
COMPANY: {job.company}
JOB DESCRIPTION:
{job.description[:2000]}

CANDIDATE RESUME:
{base_resume_text[:2000]}

Respond ONLY in valid JSON, no markdown:
{{
  "required_skills": ["skill1", "skill2"],
  "nice_to_have": ["skill3"],
  "experience_required": "0-2 years",
  "match_score": 85,
  "match_reasoning": "Short reason",
  "keywords_to_add": ["keyword1", "keyword2"],
  "should_apply": true
}}

match_score: 0-100. should_apply: true if score >= 60.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    text = response.text.strip()
    text = re.sub(r"```json|```", "", text).strip()

    try:
        parsed = json.loads(text)
        job.skills_required = parsed.get("required_skills", [])
        job.experience_required = parsed.get("experience_required", "")
        job.match_score = float(parsed.get("match_score", 0))
        return job, parsed
    except Exception as e:
        print(f"[JD Parser] JSON parse failed: {e}")
        job.match_score = 50.0
        return job, {}


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True
)
def rewrite_resume_for_job(base_resume_text: str, job: JobListing, jd_analysis: dict) -> str:
    """Return tailored resume text optimized for the job."""
    keywords = jd_analysis.get("keywords_to_add", [])
    required_skills = jd_analysis.get("required_skills", [])

    prompt = f"""
You are an expert resume writer. Tailor this resume for the job below.

TARGET JOB: {job.title} at {job.company}
REQUIRED SKILLS: {", ".join(required_skills)}
KEYWORDS TO WEAVE IN: {", ".join(keywords)}
JOB DESCRIPTION SUMMARY: {job.description[:1000]}

ORIGINAL RESUME:
{base_resume_text}

Rules:
1. Keep all factual information — never fabricate experience
2. Reorder and rephrase bullet points to highlight relevant skills
3. Add matching keywords naturally into existing bullets
4. Prioritize projects and skills matching the JD
5. Keep same overall structure and length
6. Return ONLY the updated resume text, no commentary

TAILORED RESUME:
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text.strip()
