"""TikTok bot main — runs sessions sequentially with a global lock."""
import argparse
import os
import random
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from patchright.sync_api import sync_playwright

from bitbrowser import BitBrowserClient
from actions import fyp_browse
from notify import send as notify_send

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config" / "accounts.yaml"
COMMENTS_PATH = ROOT / "config" / "comments.txt"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_DB = DATA_DIR / "actions.db"
SESSION_LOG = DATA_DIR / "sessions.log"
LOCK_FILE = DATA_DIR / "run.lock"

ACCOUNT_GAP_SECONDS = (30, 120)


def pid_alive(pid):
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock():
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip() or 0)
        except (ValueError, OSError):
            pid = 0
        if pid and pid_alive(pid):
            print(f"[error] another instance is running (PID={pid}). Exit.")
            sys.exit(1)
        print(f"[warn] stale lock from PID={pid}, removing")
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))


def release_lock():
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass


def init_db():
    conn = sqlite3.connect(LOG_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT, action TEXT, status TEXT, detail TEXT, ts TEXT
        )
    """)
    conn.commit()
    return conn


def log_action(conn, account_id, action, status, detail=""):
    conn.execute(
        "INSERT INTO action_log (account_id, action, status, detail, ts) VALUES (?,?,?,?,?)",
        (account_id, action, status, detail, datetime.now().isoformat()),
    )
    conn.commit()


def session_log(line):
    """Append one line to the human-readable sessions.log + echo to stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = f"{ts} | {line}"
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(full + "\n")
    print(full)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_comments():
    """Read the comment pool (one per line; blank / #-prefixed lines ignored)."""
    if not COMMENTS_PATH.exists():
        return []
    out = []
    for raw in COMMENTS_PATH.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def find_account(config, account_id):
    for acc in config["accounts"]:
        if acc["id"] == account_id:
            return acc
    raise ValueError(f"Account {account_id} not in config")


def run_session(account, config, conn):
    """Run one full session for one account. Returns a summary dict."""
    account_id = account["id"]
    da = config["defaults"]["daily_actions"]
    duration = random.uniform(*da["fyp_browse_minutes"])
    like_prob = float(da.get("like_probability", 0.35))
    follows_target = random.randint(*da.get("follows_per_session", [0, 1]))

    cmt_cfg = da.get("comment", {}) or {}
    comments_pool = load_comments() if cmt_cfg.get("enabled") else []
    comments_target = (
        random.randint(*cmt_cfg.get("comments_per_session", [1, 2]))
        if comments_pool else 0
    )
    comment_prob = float(cmt_cfg.get("probability", 0.25))
    comment_min_videos = int(cmt_cfg.get("min_video_comments", 1000))

    summary = {
        "account_id": account_id,
        "status": "unknown",
        "videos": 0,
        "likes": 0,
        "follows": 0,
        "comments": 0,
        "duration_target_min": round(duration, 1),
        "duration_actual_min": 0.0,
        "error": None,
    }

    bb = BitBrowserClient(config["bitbrowser"]["api_url"])
    profile_id = account["bitbrowser_profile_id"]

    if bb.is_open(profile_id):
        session_log(f"{account_id} | SKIP | profile already open")
        log_action(conn, account_id, "session", "skip", "profile already open")
        summary["status"] = "skip"
        return summary

    session_log(
        f"{account_id} | START | target={duration:.1f}min "
        f"like_p={like_prob} follows_max={follows_target} comments_max={comments_target}"
    )
    log_action(conn, account_id, "open", "start")

    started = time.time()
    try:
        cdp_url = bb.open_browser(profile_id)
        time.sleep(3)

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            log_action(conn, account_id, "fyp_browse", "start", f"duration={duration:.1f}min")
            result = fyp_browse(
                page,
                duration_minutes=duration,
                like_prob=like_prob,
                follows_target=follows_target,
                comments_target=comments_target,
                comments_pool=comments_pool,
                comment_prob=comment_prob,
                comment_min_videos=comment_min_videos,
            )
            videos = result["videos"]
            likes = result["likes"]
            follows = result["follows"]
            comments = result["comments"]

            log_action(conn, account_id, "fyp_browse", "ok", f"videos={videos}")
            if likes > 0:
                log_action(conn, account_id, "like", "ok", f"count={likes}")
            if follows > 0:
                log_action(conn, account_id, "follow", "ok", f"count={follows}")
            if comments > 0:
                log_action(conn, account_id, "comment", "ok", f"count={comments}")

            summary["videos"] = videos
            summary["likes"] = likes
            summary["follows"] = follows
            summary["comments"] = comments
            summary["status"] = "ok"

            browser.close()
        actual = (time.time() - started) / 60
        summary["duration_actual_min"] = round(actual, 1)
        session_log(
            f"{account_id} | OK | {videos}v / {likes}L / {follows}F / {comments}C "
            f"in {actual:.1f}min"
        )
    except Exception as e:
        summary["status"] = "error"
        summary["error"] = f"{type(e).__name__}: {e}"
        log_action(conn, account_id, "session", "error", str(e))
        session_log(f"{account_id} | ERROR | {summary['error']}")
    finally:
        bb.close_browser(profile_id)
        log_action(conn, account_id, "close", "ok")

    return summary


def build_batch_message(summaries):
    """Turn a list of session summaries into a notification title + body."""
    ok = sum(1 for s in summaries if s["status"] == "ok")
    err = sum(1 for s in summaries if s["status"] == "error")
    skip = sum(1 for s in summaries if s["status"] == "skip")
    total_videos = sum(s["videos"] for s in summaries)
    total = len(summaries)

    title = f"TikTok bot: {ok}/{total} OK"
    if err:
        title = f"[ERR] TikTok bot: {ok}/{total} OK, {err} failed"

    lines = [
        f"OK={ok}  ERR={err}  SKIP={skip}  videos={total_videos}",
        "",
        "Per-account:",
    ]
    for s in summaries:
        if s["status"] == "ok":
            lines.append(
                f"  - {s['account_id']}: OK "
                f"({s['videos']}v / {s['likes']}L / {s['follows']}F / {s.get('comments', 0)}C, "
                f"{s['duration_actual_min']}min)"
            )
        elif s["status"] == "error":
            lines.append(f"  - {s['account_id']}: ERROR - {s['error']}")
        else:
            lines.append(f"  - {s['account_id']}: {s['status'].upper()}")
    return title, "\n".join(lines)


def run(account_id=None):
    """Run one account, or all enabled accounts sequentially."""
    config = load_config()

    if account_id:
        accounts = [find_account(config, account_id)]
    else:
        accounts = [a for a in config["accounts"] if a.get("enabled", True)]

    if not accounts:
        print("[info] no accounts to run")
        return

    session_log(f"BATCH START | {len(accounts)} account(s)")
    conn = init_db()
    summaries = []
    try:
        for i, account in enumerate(accounts):
            summary = run_session(account, config, conn)
            summaries.append(summary)
            if i < len(accounts) - 1:
                gap = random.uniform(*ACCOUNT_GAP_SECONDS)
                print(f"[gap] sleeping {gap:.0f}s before next account")
                time.sleep(gap)
    finally:
        conn.close()

    title, body = build_batch_message(summaries)
    session_log(f"BATCH END | {title}")
    notify_send(config.get("notify", {}), title, body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default=None,
                        help="Run only this account; default: all enabled")
    args = parser.parse_args()

    acquire_lock()
    try:
        run(account_id=args.account)
    finally:
        release_lock()
