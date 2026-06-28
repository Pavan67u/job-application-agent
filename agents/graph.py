import asyncio
import os
from langgraph.graph import StateGraph, END
from agents.state import AgentState, JobListing
from agents.resume_agent import parse_jd_and_score, rewrite_resume_for_job
from resume.resume_builder import read_resume_text, save_tailored_resume
from tracker.excel_tracker import init_tracker, log_jobs
from scrapers.linkedin_scraper import scrape_linkedin, linkedin_easy_apply
from scrapers.naukri_scraper import scrape_naukri, naukri_apply
from scrapers.indeed_scraper import scrape_indeed
from config.settings import MAX_JOBS_PER_RUN, TRACKER_PATH
from playwright.async_api import async_playwright


# ── Node 1: Scrape all boards ───────────────────────────
async def scrape_node(state: AgentState) -> dict:
    print("[Node 1] Scraping jobs...")
    jobs_per_board = MAX_JOBS_PER_RUN // 3
    location = state.get("location", "Hyderabad")

    results = await asyncio.gather(
        scrape_linkedin(state["job_titles"], jobs_per_board, location),
        scrape_naukri(state["job_titles"], jobs_per_board, location),
        scrape_indeed(state["job_titles"], jobs_per_board, location),
        return_exceptions=True,
    )

    all_jobs = []
    scraper_names = ["LinkedIn", "Naukri", "Indeed"]
    for name, result in zip(scraper_names, results):
        if isinstance(result, Exception):
            print(f"[Node 1] [WARN] {name} scraper failed: {result}")
        elif isinstance(result, list):
            print(f"[Node 1] [OK] {name}: {len(result)} jobs")
            all_jobs.extend(result)
        else:
            print(f"[Node 1] [WARN] {name}: unexpected result type")

    print(f"[Node 1] Scraped {len(all_jobs)} total jobs")
    return {"raw_jobs": all_jobs}


# ── Node 2: Score and filter jobs ──────────────────────
def score_node(state: AgentState) -> dict:
    print("[Node 2] Scoring jobs...")

    if not state.get("raw_jobs"):
        print("[Node 2] No jobs to score (scrapers returned 0 jobs)")
        return {"scored_jobs": []}

    base_resume_text = read_resume_text(state["base_resume_path"])
    if not base_resume_text:
        print("[Node 2] WARNING: Could not read resume. Using empty text.")
        base_resume_text = ""

    scored = []
    jd_analyses = {}

    for job in state["raw_jobs"]:
        try:
            job, analysis = parse_jd_and_score(job, base_resume_text)
            jd_analyses[job.id] = analysis
            scored.append(job)
        except Exception as e:
            print(f"[Node 2] Score failed for {job.title} @ {job.company}: {e}")
            job.match_score = 50.0
            scored.append(job)

    # Filter — only apply to jobs with score >= 60
    apply_list = [j for j in scored if j.match_score >= 60]
    apply_list.sort(key=lambda x: x.match_score, reverse=True)

    print(f"[Node 2] {len(apply_list)}/{len(scored)} jobs pass threshold (>=60)")

    # Store analyses in state via resume_version field temporarily
    for job in apply_list:
        analysis = jd_analyses.get(job.id, {})
        job.resume_version = f"PENDING|{','.join(analysis.get('keywords_to_add', []))[:100]}"

    return {"scored_jobs": apply_list}


# ── Node 3: Tailor resume per job ──────────────────────
def tailor_resume_node(state: AgentState) -> dict:
    print("[Node 3] Tailoring resumes...")
    base_resume_text = read_resume_text(state["base_resume_path"])
    output_dir = os.path.join(os.path.dirname(state["base_resume_path"]), "tailored")

    tailored = []
    for job in state["scored_jobs"]:
        try:
            # Reconstruct jd_analysis from stored keywords
            parts = job.resume_version.split("|")
            keywords = parts[1].split(",") if len(parts) > 1 else []
            jd_analysis = {
                "keywords_to_add": [k for k in keywords if k],
                "required_skills": job.skills_required,
            }

            tailored_text = rewrite_resume_for_job(base_resume_text, job, jd_analysis)
            resume_path = save_tailored_resume(
                state["base_resume_path"],
                tailored_text,
                output_dir,
                job.id,
                job.company
            )
            job.resume_version = resume_path
            tailored.append(job)
        except Exception as e:
            print(f"[Node 3] Resume tailor failed for {job.company}: {e}")
            job.resume_version = state["base_resume_path"]
            tailored.append(job)

    return {"tailored_jobs": tailored}


# ── Node 4: Apply to jobs ──────────────────────────────
async def apply_node(state: AgentState) -> dict:
    print("[Node 4] Applying to jobs...")
    applied = []
    failed = []

    if not state.get("tailored_jobs"):
        print("[Node 4] No tailored jobs to apply to")
        return {"applied_jobs": applied, "failed_jobs": failed}

    async with async_playwright() as p:
        li_page = None
        nk_page = None
        li_browser = None
        nk_browser = None

        # LinkedIn session — wrapped in try/except
        try:
            from config.settings import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
            li_browser = await p.chromium.launch(headless=True)
            li_context = await li_browser.new_context()
            li_page = await li_context.new_page()
            await li_page.goto("https://www.linkedin.com/login", timeout=30000)
            await li_page.fill("#username", LINKEDIN_EMAIL)
            await li_page.fill("#password", LINKEDIN_PASSWORD)
            await li_page.click('[data-litms-control-urn="login-submit"]')
            await li_page.wait_for_load_state("networkidle", timeout=30000)
            print("[Node 4] LinkedIn login OK")
        except Exception as e:
            print(f"[Node 4] [WARN] LinkedIn login failed: {e}")
            li_page = None

        # Naukri session — wrapped in try/except
        try:
            from config.settings import NAUKRI_EMAIL, NAUKRI_PASSWORD
            nk_browser = await p.chromium.launch(headless=True)
            nk_context = await nk_browser.new_context()
            nk_page = await nk_context.new_page()
            await nk_page.goto("https://www.naukri.com/nlogin/login", timeout=30000)
            await asyncio.sleep(2)
            # Try multiple selectors
            for sel in ["#usernameField", 'input[type="text"]', 'input[placeholder*="Email"]']:
                el = await nk_page.query_selector(sel)
                if el:
                    await el.fill(NAUKRI_EMAIL)
                    break
            for sel in ["#passwordField", 'input[type="password"]']:
                el = await nk_page.query_selector(sel)
                if el:
                    await el.fill(NAUKRI_PASSWORD)
                    break
            for sel in ['button.loginButton', 'button[type="submit"]']:
                el = await nk_page.query_selector(sel)
                if el:
                    await el.click()
                    break
            await nk_page.wait_for_load_state("networkidle", timeout=30000)
            print("[Node 4] Naukri login OK")
        except Exception as e:
            print(f"[Node 4] [WARN] Naukri login failed: {e}")
            nk_page = None

        for job in state["tailored_jobs"]:
            try:
                success = False
                if job.source == "linkedin":
                    if li_page:
                        success = await linkedin_easy_apply(li_page, job.url)
                    else:
                        job.application_status = "failed"
                        job.error_msg = "LinkedIn login failed"
                        failed.append(job)
                        continue
                elif job.source == "naukri":
                    if nk_page:
                        success = await naukri_apply(nk_page, job.url)
                    else:
                        job.application_status = "failed"
                        job.error_msg = "Naukri login failed"
                        failed.append(job)
                        continue
                elif job.source == "indeed":
                    # Indeed requires per-company portals — mark for manual apply
                    job.application_status = "manual_required"
                    job.error_msg = "Indeed redirects to company portal"
                    failed.append(job)
                    continue

                if success:
                    job.application_status = "applied"
                    applied.append(job)
                    print(f"[Node 4] [OK] Applied: {job.title} @ {job.company}")
                else:
                    job.application_status = "failed"
                    job.error_msg = "Apply button not found or multi-step form"
                    failed.append(job)
                    print(f"[Node 4] [FAIL] Failed: {job.title} @ {job.company}")

            except Exception as e:
                job.application_status = "failed"
                job.error_msg = str(e)[:100]
                failed.append(job)
                print(f"[Node 4] [FAIL] Error: {job.title} @ {job.company}: {e}")

        if li_browser:
            await li_browser.close()
        if nk_browser:
            await nk_browser.close()

    return {"applied_jobs": applied, "failed_jobs": failed}


# ── Node 5: Log to Excel ───────────────────────────────
def log_node(state: AgentState) -> dict:
    print("[Node 5] Logging to Excel...")
    all_jobs = state.get("applied_jobs", []) + state.get("failed_jobs", [])
    log_jobs(all_jobs, state["tracker_path"])

    summary = {
        "total_scraped": len(state.get("raw_jobs", [])),
        "total_scored": len(state.get("scored_jobs", [])),
        "total_applied": len(state.get("applied_jobs", [])),
        "total_failed": len(state.get("failed_jobs", [])),
        "tracker": state["tracker_path"],
    }
    print(f"[Node 5] Summary: {summary}")
    return {"run_summary": summary}


# ── Build Graph ────────────────────────────────────────
def build_graph():
    g = StateGraph(AgentState)

    g.add_node("scrape", scrape_node)
    g.add_node("score", score_node)
    g.add_node("tailor_resume", tailor_resume_node)
    g.add_node("apply", apply_node)
    g.add_node("log", log_node)

    g.set_entry_point("scrape")
    g.add_edge("scrape", "score")
    g.add_edge("score", "tailor_resume")
    g.add_edge("tailor_resume", "apply")
    g.add_edge("apply", "log")
    g.add_edge("log", END)

    return g.compile()


async def run_agent(
    job_titles: list[str],
    location: str,
    base_resume_path: str,
    tracker_path: str = TRACKER_PATH
):
    graph = build_graph()
    init_tracker(tracker_path)

    initial_state: AgentState = {
        "job_titles": job_titles,
        "location": location,
        "base_resume_path": base_resume_path,
        "raw_jobs": [],
        "scored_jobs": [],
        "tailored_jobs": [],
        "applied_jobs": [],
        "failed_jobs": [],
        "tracker_path": tracker_path,
        "run_summary": {},
    }

    result = await graph.ainvoke(initial_state)
    return result["run_summary"]
