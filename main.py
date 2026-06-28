import asyncio
import argparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from agents.graph import run_agent
from config.settings import (
    JOB_TITLES, JOB_LOCATION, BASE_RESUME_PATH,
    TRACKER_PATH, RUN_INTERVAL_HOURS
)


async def run():
    print("\n" + "="*60)
    print("  JOB APPLICATION AGENT - STARTING RUN")
    print("="*60)
    print(f"  Titles   : {JOB_TITLES}")
    print(f"  Location : {JOB_LOCATION}")
    print(f"  Resume   : {BASE_RESUME_PATH}")
    print(f"  Tracker  : {TRACKER_PATH}")
    print("="*60 + "\n")

    summary = await run_agent(
        job_titles=JOB_TITLES,
        location=JOB_LOCATION,
        base_resume_path=BASE_RESUME_PATH,
        tracker_path=TRACKER_PATH,
    )

    print("\n" + "="*60)
    print("  RUN COMPLETE")
    print(f"  Scraped  : {summary.get('total_scraped', 0)}")
    print(f"  Scored   : {summary.get('total_scored', 0)}")
    print(f"  Applied  : {summary.get('total_applied', 0)}")
    print(f"  Failed   : {summary.get('total_failed', 0)}")
    print(f"  Tracker  : {summary.get('tracker')}")
    print("="*60 + "\n")
    return summary


async def main():
    parser = argparse.ArgumentParser(description="Job Application Agent")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=RUN_INTERVAL_HOURS, help="Run interval in hours")
    args = parser.parse_args()

    if args.once:
        await run()
        return

    # Scheduled mode
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run,
        trigger=IntervalTrigger(hours=args.interval),
        id="job_agent",
        name="Job Application Agent",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    print(f"[Scheduler] Running every {args.interval} hours. Press Ctrl+C to stop.")

    # Run once immediately on start
    await run()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[Scheduler] Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
