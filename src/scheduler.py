"""Long-running scheduler for the TikTok bot.

Mirrors the pattern of leadcrawler-service/main.py:
    FastAPI lifespan + AsyncIOScheduler.

Each day at 00:05 we generate N random fire times within the configured
active_hours. Each fire runs `main.run()` for all enabled accounts.
The existing data/run.lock file lock keeps this mutually exclusive with
any manual `python main.py` invocation.
"""
import asyncio
import argparse
import hashlib
import logging
import os
import random
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import requests
import uvicorn
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from core import runtime as main_runtime
from core.runner import run, find_account
from core.runtime import acquire_lock, pid_alive, release_lock
from runtime_config import resolve_config_path
from platform_config import account_platform, load_runtime_config, scheduler_config
from browser_providers import account_provider_name, BITBROWSER


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
CONFIG_PATH = resolve_config_path()

scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 600,
    }
)

# One browser session at a time across the whole process. Per-account fires can
# land close together; this serialises them so we never drive two profiles at once
# (the file lock only guards against a *separate* manual `python main.py`).
session_lock = asyncio.Lock()
config_fingerprint = None


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return load_runtime_config(yaml.safe_load(f))


def current_config_fingerprint():
    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


def configure_runtime(config_path=None):
    global CONFIG_PATH

    main_runtime.configure_runtime(config_path)
    CONFIG_PATH = main_runtime.CONFIG_PATH


def is_locked_externally():
    """Lock owned by another live PID (manual main.py run)."""
    if not main_runtime.LOCK_FILE.exists():
        return False
    try:
        pid = int(main_runtime.LOCK_FILE.read_text().strip() or 0)
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


def resolve_active_hours(account, cfg):
    """Account-specific active_hours, falling back to defaults."""
    platform = account_platform(account)
    platform_scheduler = scheduler_config(cfg, platform)
    return account.get("active_hours") or \
        platform_scheduler.get("active_hours", [[9, 12], [19, 23]])


async def account_session_task(account_id, job_id=None):
    """One scheduled fire for a single account.

    `main.run()` is synchronous (sync_playwright), so we offload it to the default
    thread executor. `session_lock` keeps fires from overlapping; the file lock
    inside `run` still guards against a separate manual run.
    """
    job_id = job_id or f"fire_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    platform = "tiktok"
    try:
        cfg = load_config()
        account = find_account(cfg, account_id)
        platform = account_platform(account)
        provider = account_provider_name(account, cfg)
    except Exception as e:
        detail = f"could not resolve account config: {e}"
        main_runtime.record_scheduler_job_started(job_id, platform, account_id)
        main_runtime.record_scheduler_job_finished(job_id, "skipped", detail)
        logger.error(f"Fire aborted: {account_id} — {detail}")
        return

    main_runtime.record_scheduler_job_started(job_id, platform, account_id)

    if provider == BITBROWSER and not bitbrowser_responsive():
        detail = "BitBrowser API unreachable on 127.0.0.1:54345. Is the BitBrowser app running?"
        main_runtime.record_scheduler_job_finished(job_id, "skipped", detail)
        logger.error(f"Skipped {account_id} — {detail}")
        return

    async with session_lock:
        logger.info(f"Fire start: {account_id}")
        loop = asyncio.get_event_loop()

        def sync_call():
            if is_locked_externally():
                return ("skipped", "manual run holds the lock")
            try:
                acquire_lock()
            except SystemExit:
                return ("skipped", "lock taken between check and acquire")
            try:
                summaries = run(account_id=account_id)
            finally:
                release_lock()
            if not summaries:
                return ("skipped", "no executable account runner")
            failed = [item for item in summaries if item.get("status") == "error"]
            skipped = [item for item in summaries if item.get("status") == "skip"]
            if failed:
                return ("failed", failed[0].get("error") or "account run failed")
            if skipped:
                return ("skipped", skipped[0].get("error") or "account run skipped")
            return ("success", "")

        try:
            status, detail = await loop.run_in_executor(None, sync_call)
            main_runtime.record_scheduler_job_finished(job_id, status, detail)
            if status == "skipped":
                logger.warning(f"Skipped {account_id} — {detail}")
            elif status == "failed":
                logger.error(f"Fire failed: {account_id} — {detail}")
        except Exception as e:
            main_runtime.record_scheduler_job_finished(job_id, "failed", str(e))
            logger.error(f"Fire failed: {account_id} — {e}", exc_info=True)
        logger.info(f"Fire end: {account_id}")


def generate_fire_times(active_hours, count, base_date=None):
    """N random datetimes within `active_hours` of `base_date`."""
    if base_date is None:
        base_date = datetime.now()
    base = base_date.replace(hour=0, minute=0, second=0, microsecond=0)

    fires = []
    for _ in range(count):
        window = random.choice(active_hours)
        start_h, end_h = window
        start_minute = int(round(float(start_h) * 60))
        end_minute = int(round(float(end_h) * 60))
        total_minutes = max(1, end_minute - start_minute)
        offset = random.randint(0, total_minutes - 1)
        s = random.randint(0, 59)
        fires.append(base + timedelta(minutes=start_minute + offset, seconds=s))
    return sorted(fires)


def _windows_overlap(a, b):
    """True if any hour-window in active_hours `a` overlaps one in `b`."""
    for s1, e1 in a:
        for s2, e2 in b:
            if s1 < e2 and s2 < e1:
                return True
    return False


def executable_accounts(cfg):
    return [
        account
        for account in cfg["accounts"]
        if account.get("enabled", True)
        and account.get("scheduled", True)
        and str(account.get("platform", "tiktok")).strip().lower() == "tiktok"
    ]


def validate_ip_groups(cfg):
    """Warn if two enabled accounts share an ip_group (same IP) AND overlapping
    active_hours — that risks two profiles on one IP being active at once.

    The shift model relies on same-IP accounts living in non-overlapping windows
    (e.g. one morning, one evening). This catches a misassignment early.
    """
    accounts = executable_accounts(cfg)
    by_group = {}
    for acc in accounts:
        g = acc.get("ip_group")
        if g is not None:
            by_group.setdefault(g, []).append(acc)

    for g, members in by_group.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if _windows_overlap(resolve_active_hours(a, cfg),
                                    resolve_active_hours(b, cfg)):
                    logger.warning(
                        f"ip_group {g}: {a['id']} and {b['id']} share an IP but have "
                        f"OVERLAPPING active_hours — put them in different shifts "
                        f"(e.g. one morning, one evening) so they never run together."
                    )


def schedule_today_fires():
    """Generate today's remaining fires — per account, within its own active_hours.

    Same-IP isolation comes from the shift model (same-IP accounts live in
    non-overlapping windows), not from spacing here. Accounts run one at a time
    via `session_lock`, so within a shift distinct-IP accounts are simply queued.
    """
    global config_fingerprint

    cfg = load_config()
    sched_cfg = scheduler_config(cfg, "tiktok")
    fires_per_day = int(sched_cfg.get("fires_per_day", 3))
    accounts = executable_accounts(cfg)

    for job in scheduler.get_jobs():
        if job.id.startswith("fire_"):
            scheduler.remove_job(job.id)

    now = datetime.now()
    total = 0

    for acc in accounts:
        acc_id = acc["id"]
        group = acc.get("ip_group")
        active_hours = resolve_active_hours(acc, cfg)

        fires = [f for f in generate_fire_times(active_hours, fires_per_day) if f > now]
        for f in fires:
            job_id = f"fire_{acc_id}_{f.strftime('%Y%m%d_%H%M%S')}"
            scheduler.add_job(
                account_session_task,
                trigger="date",
                run_date=f,
                id=job_id,
                args=[acc_id, job_id],
                replace_existing=True,
            )
            main_runtime.record_scheduler_job_scheduled(
                job_id,
                account_platform(acc),
                acc_id,
                f.isoformat(),
            )
            logger.info(f"Scheduled {acc_id} at {f.isoformat()} (ip_group={group})")
        total += len(fires)

    if total == 0:
        logger.warning("No fires scheduled for today (active_hours already past)")
    config_fingerprint = current_config_fingerprint()


def reload_schedule_if_config_changed():
    try:
        fingerprint = current_config_fingerprint()
    except OSError as exc:
        logger.error(f"Failed to inspect scheduler config: {exc}")
        return

    if fingerprint == config_fingerprint:
        return

    logger.info("accounts.yaml changed; rebuilding remaining scheduler jobs")
    try:
        validate_ip_groups(load_config())
        schedule_today_fires()
    except Exception as exc:
        logger.error(f"Failed to reload scheduler config: {exc}", exc_info=True)


def setup_scheduler():
    validate_ip_groups(load_config())
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
    scheduler.add_job(
        reload_schedule_if_config_changed,
        trigger="interval",
        seconds=10,
        id="config_reload",
        replace_existing=True,
    )
    logger.info("Config reload check set for every 10 seconds")


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
    return {"service": "account-matrix scheduler"}


@app.get("/health")
async def health():
    jobs = []
    for j in scheduler.get_jobs():
        jobs.append({
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        })
    return {
        "status": "ok",
        "process_id": os.getpid(),
        "config_path": str(CONFIG_PATH.resolve()),
        "jobs": jobs,
        "lock_held_externally": is_locked_externally(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None,
                        help="Path to accounts.yaml; default: config/accounts.yaml")
    parser.add_argument("--data-dir", default=None,
                        help="Runtime data directory; default: data next to config")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Scheduler host; default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=9601,
                        help="Scheduler port; default: 9601")
    args = parser.parse_args()
    if args.data_dir:
        os.environ["AM_DATA_DIR"] = args.data_dir
    configure_runtime(args.config)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
