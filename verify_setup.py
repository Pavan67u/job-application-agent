"""Quick verification script for Job Application Agent setup."""
import sys

checks = []

# 1. Google Genai
try:
    from google import genai
    checks.append(("google-genai import", "OK"))
except Exception as e:
    checks.append(("google-genai import", f"FAIL: {e}"))

# 2. State imports
try:
    from agents.state import AgentState, JobListing
    checks.append(("State imports", "OK"))
except Exception as e:
    checks.append(("State imports", f"FAIL: {e}"))

# 3. Config
try:
    from config.settings import GEMINI_API_KEY, LINKEDIN_EMAIL, NAUKRI_EMAIL
    key_status = "SET" if GEMINI_API_KEY else "MISSING"
    li_status = "SET" if LINKEDIN_EMAIL else "MISSING"
    nk_status = "SET" if NAUKRI_EMAIL else "MISSING"
    checks.append(("Gemini API Key", key_status))
    checks.append(("LinkedIn Email", li_status))
    checks.append(("Naukri Email", nk_status))
except Exception as e:
    checks.append(("Config load", f"FAIL: {e}"))

# 4. Resume read
try:
    from resume.resume_builder import read_resume_text
    text = read_resume_text("data/resumes/base_resume.docx")
    checks.append(("Resume read", f"OK ({len(text)} chars)"))
except Exception as e:
    checks.append(("Resume read", f"FAIL: {e}"))

# 5. Tracker
try:
    from tracker.excel_tracker import init_tracker
    checks.append(("Tracker import", "OK"))
except Exception as e:
    checks.append(("Tracker import", f"FAIL: {e}"))

# 6. Graph build
try:
    from agents.graph import build_graph
    g = build_graph()
    checks.append(("Graph build", "OK"))
except Exception as e:
    checks.append(("Graph build", f"FAIL: {e}"))

# Print results
print("\n" + "=" * 50)
print("  JOB APPLICATION AGENT - SETUP CHECK")
print("=" * 50)
all_ok = True
for name, status in checks:
    icon = "+" if "OK" in status or "SET" in status else "X"
    print(f"  [{icon}] {name}: {status}")
    if "FAIL" in status or "MISSING" in status:
        all_ok = False
print("=" * 50)
if all_ok:
    print("  ALL CHECKS PASSED")
else:
    print("  SOME CHECKS FAILED - see above")
print("=" * 50 + "\n")
