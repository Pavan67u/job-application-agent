import asyncio
import random
import uuid
from datetime import datetime
from playwright.async_api import async_playwright
from config.settings import NAUKRI_EMAIL, NAUKRI_PASSWORD, JOB_LOCATION
from agents.state import JobListing


async def _try_fill(page, selectors: list[str], value: str, field_name: str) -> bool:
    """Try multiple selectors to fill a field. Returns True if successful."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                return True
        except Exception:
            continue
    print(f"[Naukri] Could not find {field_name} field with any known selector")
    return False


async def _try_click(page, selectors: list[str], button_name: str) -> bool:
    """Try multiple selectors to click a button. Returns True if successful."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                return True
        except Exception:
            continue
    print(f"[Naukri] Could not find {button_name} button with any known selector")
    return False


async def scrape_naukri(job_titles: list[str], max_jobs: int = 20, location: str = None) -> list[JobListing]:
    loc = location or JOB_LOCATION
    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Login to Naukri — try multiple known selectors
        logged_in = False
        try:
            await page.goto("https://www.naukri.com/nlogin/login", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))

            # Username — try multiple selectors
            username_filled = await _try_fill(page, [
                "#usernameField",
                'input[placeholder*="Email"]',
                'input[placeholder*="email"]',
                'input[type="text"]',
                'input[name="usernameField"]',
                'form input:first-of-type',
            ], NAUKRI_EMAIL, "username")

            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Password
            password_filled = await _try_fill(page, [
                "#passwordField",
                'input[placeholder*="Password"]',
                'input[placeholder*="password"]',
                'input[type="password"]',
                'input[name="passwordField"]',
            ], NAUKRI_PASSWORD, "password")

            await asyncio.sleep(random.uniform(0.5, 1.0))

            if username_filled and password_filled:
                # Login button
                await _try_click(page, [
                    'button.loginButton',
                    'button[type="submit"]',
                    'button:has-text("Login")',
                    '.loginButton',
                    'form button',
                ], "login")

                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))
                logged_in = True
                print("[Naukri] Login successful")
            else:
                print("[Naukri] Login fields not found, continuing without login")

        except Exception as e:
            print(f"[Naukri] Login error: {e}")
            print("[Naukri] Continuing without login...")

        # Search jobs (works with or without login)
        for title in job_titles:
            if len(jobs) >= max_jobs:
                break

            keyword = title.replace(" ", "-").lower()
            loc_slug = loc.replace(" ", "-").lower()
            search_url = (
                f"https://www.naukri.com/{keyword}"
                f"-jobs-in-{loc_slug}?experience=0&jobAge=1"
            )

            try:
                await page.goto(search_url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                # Try multiple card selectors (Naukri changes these)
                job_cards = await page.query_selector_all(".jobTuple")
                if not job_cards:
                    job_cards = await page.query_selector_all("[data-job-id]")
                if not job_cards:
                    job_cards = await page.query_selector_all(".srp-jobtuple-wrapper")
                if not job_cards:
                    job_cards = await page.query_selector_all("article.jobTuple")

                print(f"[Naukri] Found {len(job_cards)} cards for '{title}'")

                for card in job_cards[:max_jobs]:
                    try:
                        # Try multiple title selectors
                        title_el = await card.query_selector(".title")
                        if not title_el:
                            title_el = await card.query_selector("a.title")
                        if not title_el:
                            title_el = await card.query_selector("h2 a")

                        company_el = await card.query_selector(".companyInfo .company")
                        if not company_el:
                            company_el = await card.query_selector(".comp-name")
                        if not company_el:
                            company_el = await card.query_selector("[class*='company']")

                        location_el = await card.query_selector(".location")
                        if not location_el:
                            location_el = await card.query_selector(".loc")
                        if not location_el:
                            location_el = await card.query_selector("[class*='location']")

                        link_el = await card.query_selector("a.title")
                        if not link_el:
                            link_el = await card.query_selector("a[href*='naukri.com']")
                        if not link_el:
                            link_el = await card.query_selector("a")

                        title_text = await title_el.inner_text() if title_el else ""
                        company_text = await company_el.inner_text() if company_el else ""
                        location_text = await location_el.inner_text() if location_el else ""
                        href = await link_el.get_attribute("href") if link_el else ""

                        if not href:
                            continue

                        # Get description
                        description = ""
                        try:
                            desc_page = await context.new_page()
                            await desc_page.goto(href, timeout=20000)
                            await desc_page.wait_for_load_state("networkidle", timeout=15000)
                            for sel in [".job-desc", ".jd-desc", "#job-desc", ".styles_JDC__dang-inner-html__h0K4t", "[class*='job-desc']"]:
                                desc_el = await desc_page.query_selector(sel)
                                if desc_el:
                                    description = await desc_el.inner_text()
                                    break
                            await desc_page.close()
                        except Exception:
                            pass

                        jobs.append(JobListing(
                            id=str(uuid.uuid4())[:8],
                            title=title_text.strip(),
                            company=company_text.strip(),
                            location=location_text.strip(),
                            url=href,
                            source="naukri",
                            description=description[:3000],
                            posted_date=datetime.now().strftime("%Y-%m-%d"),
                        ))

                        if len(jobs) >= max_jobs:
                            break

                        await asyncio.sleep(random.uniform(1, 2.5))

                    except Exception as e:
                        print(f"[Naukri] Card parse error: {e}")
                        continue

            except Exception as e:
                print(f"[Naukri] Search error for '{title}': {e}")
                continue

        await browser.close()
    print(f"[Naukri] Scraped {len(jobs)} jobs total")
    return jobs


async def naukri_apply(page, job_url: str) -> bool:
    """Apply to a Naukri job."""
    try:
        await page.goto(job_url)
        await page.wait_for_load_state("networkidle")

        apply_btn = await page.query_selector('button[id="apply-button"]')
        if not apply_btn:
            apply_btn = await page.query_selector('.apply-button')
        if not apply_btn:
            apply_btn = await page.query_selector('button:has-text("Apply")')

        if not apply_btn:
            return False

        await apply_btn.click()
        await page.wait_for_timeout(2000)

        # Confirm apply modal if present
        confirm_btn = await page.query_selector('.modal-apply-btn')
        if not confirm_btn:
            confirm_btn = await page.query_selector('button:has-text("Apply on company")')
        if confirm_btn:
            await confirm_btn.click()
            await page.wait_for_timeout(2000)

        return True

    except Exception as e:
        print(f"[Naukri Apply] Error: {e}")
        return False
