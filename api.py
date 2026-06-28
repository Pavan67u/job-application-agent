import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os

from agents.graph import run_agent
from tracker.excel_tracker import init_tracker
from config.settings import JOB_TITLES, JOB_LOCATION, BASE_RESUME_PATH, TRACKER_PATH

app = FastAPI(title="Job Application Agent API", version="1.0.0")

# Track current run state
_run_state = {"running": False, "last_summary": None}


class RunRequest(BaseModel):
    job_titles: Optional[list[str]] = None
    location: Optional[str] = None
    resume_path: Optional[str] = None


@app.get("/")
def root():
    return {"status": "Job Agent API running"}


@app.get("/health")
def health():
    return {"healthy": True, "running": _run_state["running"]}


@app.post("/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    if _run_state["running"]:
        raise HTTPException(status_code=409, detail="Agent already running")

    titles = req.job_titles or JOB_TITLES
    location = req.location or JOB_LOCATION
    resume = req.resume_path or BASE_RESUME_PATH

    async def _run():
        _run_state["running"] = True
        try:
            summary = await run_agent(titles, location, resume, TRACKER_PATH)
            _run_state["last_summary"] = summary
        except Exception as e:
            _run_state["last_summary"] = {"error": str(e)}
        finally:
            _run_state["running"] = False

    background_tasks.add_task(_run)
    return {"message": "Agent run started", "titles": titles, "location": location}


@app.get("/status")
def status():
    return {
        "running": _run_state["running"],
        "last_summary": _run_state["last_summary"],
    }


@app.get("/download/tracker")
def download_tracker():
    if not os.path.exists(TRACKER_PATH):
        raise HTTPException(status_code=404, detail="Tracker not found. Run agent first.")
    return FileResponse(
        TRACKER_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="job_tracker.xlsx"
    )


@app.get("/download/resumes")
def list_resumes():
    resume_dir = os.path.join(os.path.dirname(BASE_RESUME_PATH), "tailored")
    if not os.path.exists(resume_dir):
        return {"resumes": []}
    files = [f for f in os.listdir(resume_dir) if f.endswith(".docx")]
    return {"resumes": sorted(files, reverse=True)}


@app.get("/download/resume/{filename}")
def download_resume(filename: str):
    resume_dir = os.path.join(os.path.dirname(BASE_RESUME_PATH), "tailored")
    path = os.path.join(resume_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Resume not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )
