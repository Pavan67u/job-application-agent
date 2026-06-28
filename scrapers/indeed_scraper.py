import asyncio
import random
import uuid
from datetime import datetime
from playwright.async_api import async_playwright
from config.settings import JOB_LOCATION
from agents.state import JobListing


async def scrape_indeed(job_titles: list[str], max_jobs: int = 20, location: str = None) -> list[JobListing]:
    loc = location or JOB_LOCATION
    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for title in job_titles:
            if len(jobs) >= max_jobs:
                break

            keyword = title.replace(" ", "+")
            loc_encoded = loc.replace(" ", "+")
            search_url = (
                f"https://in.indeed.com/jobs?q={keyword}"
                f"&l={loc_encoded}&explvl=entry_level&fromage=1&sort=date"
            )

            try:
                await page.goto(search_url, timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                job_cards = await page.query_selector_all(".job_seen_beacon")
                if not job_cards:
                    job_cards = await page.query_selector_all("[data-jk]")
                if not job_cards:
                    job_cards = await page.query_selector_all(".result")

                print(f"[Indeed] Found {len(job_cards)} cards for '{title}'")

                for card in job_cards[:max_jobs]:
                    try:
                        title_el = await card.query_selector('[data-testid="jobTitle"]')
                        if not title_el:
                            title_el = await card.query_selector("h2 a span")
                        company_el = await card.query_selector('[data-testid="company-name"]')
                        if not company_el:
                            company_el = await card.query_selector("[class*='company']")
                        location_el = await card.query_selector('[data-testid="text-location"]')
                        if not location_el:
                            location_el = await card.query_selector("[class*='location']")
                        link_el = await card.query_selector('a[id^="job_"]')
                        if not link_el:
                            link_el = await card.query_selector("h2 a")

                        title_text = await title_el.inner_text() if title_el else ""
                        company_text = await company_el.inner_text() if company_el else ""
                        location_text = await location_el.inner_text() if location_el else ""
                        href = await link_el.get_attribute("href") if link_el else ""

                        if not href:
                            continue

                        full_url = f"https://in.indeed.com{href}" if href.startswith("/") else href

                        # Get description
                        description = ""
                        try:
                            desc_page = await context.new_page()
                            await desc_page.goto(full_url, timeout=20000)
                            await desc_page.wait_for_load_state("networkidle", timeout=15000)
                            for sel in ["#jobDescriptionText", ".jobsearch-JobComponent-description", "[class*='jobDescription']"]:
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
                            url=full_url,
                            source="indeed",
                            description=description[:3000],
                            posted_date=datetime.now().strftime("%Y-%m-%d"),
                        ))

                        if len(jobs) >= max_jobs:
                            break

                        await asyncio.sleep(random.uniform(1, 2.5))

                    except Exception as e:
                        print(f"[Indeed] Card parse error: {e}")
                        continue

            except Exception as e:
                print(f"[Indeed] Search error for '{title}': {e}")
                continue

        await browser.close()
    print(f"[Indeed] Scraped {len(jobs)} jobs total")
    return jobs
