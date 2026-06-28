# Job Application Agent 🤖

Automated job scraper, resume tailor, applicant, and Excel tracker.
Built with LangGraph + Claude API + Playwright.

---

## Architecture

```
[Scrape Node]      → LinkedIn + Naukri + Indeed
      ↓
[Score Node]       → Claude parses JD, scores match %
      ↓
[Tailor Resume]    → Claude rewrites resume per job
      ↓
[Apply Node]       → Playwright auto-applies (Easy Apply / Naukri)
      ↓
[Log Node]         → Excel tracker with color-coded dashboard
```

---

## Setup

### 1. Clone & install

```bash
cd job_agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials and settings
```

### 3. Add your resume

Place your resume DOCX at:
```
data/resumes/base_resume.docx
```

---

## Run

### Single run
```bash
python main.py --once
```

### Auto-scheduled (every 12 hours)
```bash
python main.py
```

### Custom interval
```bash
python main.py --interval 6
```

### Via FastAPI (REST)
```bash
uvicorn api:app --reload --port 8000

# Trigger run
POST http://localhost:8000/run

# Check status
GET  http://localhost:8000/status

# Download tracker
GET  http://localhost:8000/download/tracker

# List tailored resumes
GET  http://localhost:8000/download/resumes
```

---

## Output

### Excel Tracker (`data/output/job_tracker.xlsx`)

| Column | Description |
|---|---|
| Job ID | Unique ID per job |
| Date Applied | Timestamp |
| Job Title | Role name |
| Company | Company name |
| Location | City |
| Source | linkedin / naukri / indeed |
| Match Score | 0-100 color scale |
| Status | applied / failed / manual |
| Resume Version | Path to tailored DOCX |
| Job URL | Direct link |
| Skills Required | Extracted from JD |
| Notes | Error messages |
| Follow Up Date | Manual fill |
| Response | Manual fill |

### Tailored Resumes (`data/resumes/tailored/`)
```
resume_Google_a1b2_20240626_1430.docx
resume_Infosys_c3d4_20240626_1431.docx
```

---

## Platform Notes

| Platform | Method | Notes |
|---|---|---|
| LinkedIn | Easy Apply via Playwright | Works for single + multi-step |
| Naukri | Apply button via Playwright | Works for direct apply |
| Indeed | Scrape only | Redirects to company portals; marked `manual_required` |

---

## Configuration (`.env`)

```env
ANTHROPIC_API_KEY=sk-ant-...
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
NAUKRI_EMAIL=your@email.com
NAUKRI_PASSWORD=yourpassword

JOB_TITLES=Software Engineer,Full Stack Developer,Data Analyst,ML Engineer
JOB_LOCATION=Hyderabad
EXPERIENCE_YEARS=0
MAX_JOBS_PER_RUN=20
RUN_INTERVAL_HOURS=12
BASE_RESUME_PATH=data/resumes/base_resume.docx
TRACKER_PATH=data/output/job_tracker.xlsx
```

---

## Project Structure

```
job_agent/
├── main.py                    # Entry point + scheduler
├── api.py                     # FastAPI REST API
├── requirements.txt
├── .env.example
├── agents/
│   ├── state.py               # LangGraph AgentState schema
│   ├── graph.py               # LangGraph nodes + graph wiring
│   └── resume_agent.py        # Claude JD parser + resume rewriter
├── scrapers/
│   ├── linkedin_scraper.py    # LinkedIn scraper + Easy Apply
│   ├── naukri_scraper.py      # Naukri scraper + apply
│   └── indeed_scraper.py      # Indeed scraper
├── resume/
│   └── resume_builder.py      # DOCX reader + tailored resume writer
├── tracker/
│   └── excel_tracker.py       # openpyxl tracker with dashboard
├── config/
│   └── settings.py            # Env config loader
└── data/
    ├── resumes/
    │   ├── base_resume.docx   ← PUT YOUR RESUME HERE
    │   └── tailored/          ← Auto-generated per job
    └── output/
        └── job_tracker.xlsx   ← Auto-generated tracker
```

---

## Add to GitHub

```bash
git init
git add .
git commit -m "feat: job application agent - LangGraph + Claude + Playwright"
git remote add origin https://github.com/Pavan67u/job-application-agent.git
git push -u origin main
```
