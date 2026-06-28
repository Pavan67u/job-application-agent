import asyncio
import random
import uuid
from datetime import datetime
from playwright.async_api import async_playwright
from config.settings import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, JOB_LOCATION
from agents.state import JobListing


async def scrape_linkedin(job_titles: list[str], max_jobs: int = 20, location: str = None) -> list[JobListing]:
    loc = location or JOB_LOCATION
    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Login
        try:
            await page.goto("https://www.linkedin.com/login", timeout=30000)
            await page.fill("#username", LINKEDIN_EMAIL)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.fill("#password", LINKEDIN_PASSWORD)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.click('[data-litms-control-urn="login-submit"]')
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))

            # Check if login succeeded
            if "login" in page.url.lower() or "challenge" in page.url.lower():
                print("[LinkedIn] Login failed or CAPTCHA detected, scraping public listings")
        except Exception as e:
            print(f"[LinkedIn] Login error: {e}")
            print("[LinkedIn] Continuing with public job search...")

        for title in job_titles:
            if len(jobs) >= max_jobs:
                break

            search_url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={title.replace(' ', '%20')}"
                f"&location={loc.replace(' ', '%20')}"
                f"&f_E=1%2C2"  # Entry level + Associate
                f"&f_TPR=r86400"  # Last 24hrs
                f"&sortBy=DD"
            )

            try:
                await page.goto(search_url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                # Scroll to load more
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(random.uniform(1, 2))

                job_cards = await page.query_selector_all(".job-search-card")
                if not job_cards:
                    job_cards = await page.query_selector_all("[data-entity-urn]")
                print(f"[LinkedIn] Found {len(job_cards)} cards for '{title}'")

                for card in job_cards[:max_jobs]:
                    try:
                        job_title = await card.query_selector(".job-search-card__title")
                        company = await card.query_selector(".job-search-card__company-name")
                        loc_el = await card.query_selector(".job-search-card__location")
                        link = await card.query_selector("a.job-search-card__title-link")
                        if not link:
                            link = await card.query_selector("a")

                        title_text = await job_title.inner_text() if job_title else ""
                        company_text = await company.inner_text() if company else ""
                        location_text = await loc_el.inner_text() if loc_el else ""
                        href = await link.get_attribute("href") if link else ""

                        if not href:
                            continue

                        # Get job description
                        description = ""
                        try:
                            desc_page = await context.new_page()
                            await desc_page.goto(href, timeout=20000)
                            await desc_page.wait_for_load_state("networkidle", timeout=15000)
                            for sel in [".jobs-description__content", ".description__text", ".show-more-less-html__markup"]:
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
                            url=href.split("?")[0],
                            source="linkedin",
                            description=description[:3000],
                            posted_date=datetime.now().strftime("%Y-%m-%d"),
                        ))

                        if len(jobs) >= max_jobs:
                            break

                        await asyncio.sleep(random.uniform(1, 2.5))

                    except Exception as e:
                        print(f"[LinkedIn] Card parse error: {e}")
                        continue

            except Exception as e:
                print(f"[LinkedIn] Search error for '{title}': {e}")
                continue

        await browser.close()
    print(f"[LinkedIn] Scraped {len(jobs)} jobs total")
    return jobs


async def linkedin_easy_apply(page, job_url: str) -> bool:
    """Attempt LinkedIn Easy Apply on a job."""
    try:
        await page.goto(job_url)
        await page.wait_for_load_state("networkidle")

        # Click Easy Apply button
        easy_apply_btn = await page.query_selector(".jobs-apply-button--top-card")
        if not easy_apply_btn:
            return False

        btn_text = await easy_apply_btn.inner_text()
        if "Easy Apply" not in btn_text:
            return False

        await easy_apply_btn.click()
        await page.wait_for_timeout(2000)

        # Handle multi-step form — submit if single page
        submit_btn = await page.query_selector('button[aria-label="Submit application"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_timeout(2000)
            return True

        # If multi-step, click through Next buttons
        for _ in range(5):
            next_btn = await page.query_selector('button[aria-label="Continue to next step"]')
            if next_btn:
                await next_btn.click()
                await page.wait_for_timeout(1500)
            else:
                break

        submit_btn = await page.query_selector('button[aria-label="Submit application"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_timeout(2000)
            return True

        return False

    except Exception as e:
        print(f"[LinkedIn EasyApply] Error: {e}")
        return False
