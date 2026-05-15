"""Long-running scheduler for the TikTok bot.

Mirrors the pattern of leadcrawler-service/main.py:
    FastAPI lifespan + AsyncIOScheduler.

Each day at 00:05 we generate N random fire times within the configured
active_hours. Each fire runs `main.run()` for all enabled accounts.
The existing data/run.lock file lock keeps this mutually exclusive with
any manual `python main.py` invocation.
"""
import asyncio
import logging
import os
import random
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import requests
import uvicorn
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from main import LOCK_FILE, acquire_lock, pid_alive, release_lock, run


def setup_windows_event_loop():
    if sys.platform.startswith("win") and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


setup_windows_event_loop()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("scheduler")

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config" / "accounts.yaml"

scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 600,
    }
)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_locked_externally():
    """Lock owned by another live PID (manual main.py run)."""
    if not LOCK_FILE.exists():
        return False
    try:
        pid = int(LOCK_FILE.read_text().strip() or 0)
    except (ValueError, OSError):
        return False
    return bool(pid) and pid_alive(pid) and pid != os.getpid()


def bitbrowser_responsive():
    """Cheap probe — can BitBrowser API answer within 5s?"""
    cfg = load_config()
    api_url = cfg["bitbrowser"]["api_url"].rstrip("/")
    try:
        resp = requests.post(
            f"{api_url}/browser/pids",
            json={"ids": []},
            timeout=5,
        )
        return resp.ok
    except Exception as e:
        logger.warning(f"BitBrowser probe failed: {e}")
        return False


async def batch_session_task():
    """One scheduled fire: run all enabled accounts sequentially.

    `main.run()` is synchronous (uses sync_playwright), so we offload it to
    the default thread executor.
    """
    if is_locked_externally():
        logger.warning("Skipped fire — another instance holds the lock")
        return

    if not bitbrowser_responsive():
        logger.error(
            "Skipped fire — BitBrowser API unreachable on 127.0.0.1:54345. "
            "Is the BitBrowser app running?"
        )
        return

    logger.info("Batch fire start")
    loop = asyncio.get_event_loop()

    def sync_call():
        try:
            acquire_lock()
        except SystemExit:
            logger.warning("Lock acquired between check and acquire — skipping")
            return
        try:
            run(account_id=None)
        finally:
            release_lock()

    try:
        await loop.run_in_executor(None, sync_call)
    except Exception as e:
        logger.error(f"Batch fire failed: {e}", exc_info=True)
    logger.info("Batch fire end")


def generate_fire_times(active_hours, count, base_date=None):
    """N random datetimes within `active_hours` of `base_date`."""
    if base_date is None:
        base_date = datetime.now()
    base = base_date.replace(microsecond=0)

    fires = []
    for _ in range(count):
        window = random.choice(active_hours)
        start_h, end_h = window
        total_minutes = max(1, (end_h - start_h) * 60)
        offset = random.randint(0, total_minutes - 1)
        h = start_h + offset // 60
        m = offset % 60
        s = random.randint(0, 59)
        fires.append(base.replace(hour=h, minute=m, second=s))
    return sorted(fires)


def schedule_today_fires():
    """Generate today's remaining fires from config."""
    cfg = load_config()
    sched_cfg = cfg.get("scheduler", {})
    fires_per_day = int(sched_cfg.get("fires_per_day", 3))
    active_hours = cfg["defaults"].get("active_hours", [[9, 12], [19, 23]])

    now = datetime.now()
    fires = [f for f in generate_fire_times(active_hours, fires_per_day) if f > now]

    for f in fires:
        job_id = f"fire_{f.strftime('%Y%m%d_%H%M%S')}"
        scheduler.add_job(
            batch_session_task,
            trigger="date",
            run_date=f,
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled fire at {f.isoformat()}")

    if not fires:
        logger.warning("No fires scheduled for today (active_hours already past)")


def setup_scheduler():
    schedule_today_fires()
    # Roll over to the new day's schedule at 00:05.
    scheduler.add_job(
        schedule_today_fires,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_reschedule",
        replace_existing=True,
    )
    logger.info("Daily reschedule job set for 00:05")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("TikTok bot scheduler starting...")
    if bitbrowser_responsive():
        logger.info("BitBrowser health check OK")
    else:
        logger.warning(
            "BitBrowser API not responsive at startup. "
            "Scheduler will run, but fires will skip until the app is reachable."
        )
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler running")
    try:
        yield
    finally:
        logger.info("Scheduler stopping...")
        scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"service": "tiktok-bot scheduler"}


@app.get("/health")
async def health():
    jobs = []
    for j in scheduler.get_jobs():
        jobs.append({
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        })
    return {"status": "ok", "jobs": jobs, "lock_held_externally": is_locked_externally()}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9601, log_level="info")
