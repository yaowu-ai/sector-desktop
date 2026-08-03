"""Shared runtime state, logging, DB, and config helpers."""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from runtime_config import (
    resolve_comments_path,
    resolve_config_path,
    resolve_data_dir,
    resolve_path,
)
from platform_config import (
    comments_config,
    load_runtime_config,
    normalize_platform,
)

CONFIG_PATH = resolve_config_path()
DATA_DIR = resolve_data_dir(CONFIG_PATH)
COMMENTS_PATH = resolve_comments_path("comments.txt", CONFIG_PATH)
LOG_DB = DATA_DIR / "actions.db"
SESSION_LOG = DATA_DIR / "sessions.log"
LOCK_FILE = DATA_DIR / "run.lock"
STOP_AFTER_CURRENT_FILE = DATA_DIR / "stop_after_current.flag"
DATA_DIR.mkdir(exist_ok=True)

BROWSER_PREVIEW_PREFIX = "AM_BROWSER_PREVIEW "
AUTH_EVENT_PREFIX = "AM_AUTH_EVENT "

PROXY_URL_CREDENTIAL_RE = re.compile(
    r"\b((?:https?|socks5)://[^:\s/@]+:)([^@\s]+)(@[^\s]+)",
    re.IGNORECASE,
)
COLON_PROXY_CREDENTIAL_RE = re.compile(r"(?<!\S)([^:\s]+:\d{1,5}:[^:\s]+:)([^\s]+)")
SENSITIVE_KEY_VALUE_RE = re.compile(
    r"\b(password|passwd|proxy_password|proxy password|credential|credentials|token|cookie|session)\b"
    r"(\s*[:=]\s*)"
    r"([^;\s,}\]]+)",
    re.IGNORECASE,
)


def configure_runtime(config_path=None):
    global CONFIG_PATH, COMMENTS_PATH, DATA_DIR, LOG_DB, SESSION_LOG, LOCK_FILE
    global STOP_AFTER_CURRENT_FILE

    CONFIG_PATH = resolve_config_path(config_path)
    DATA_DIR = resolve_data_dir(CONFIG_PATH)
    DATA_DIR.mkdir(exist_ok=True)
    COMMENTS_PATH = resolve_comments_path("comments.txt", CONFIG_PATH)
    LOG_DB = DATA_DIR / "actions.db"
    SESSION_LOG = DATA_DIR / "sessions.log"
    LOCK_FILE = DATA_DIR / "run.lock"
    STOP_AFTER_CURRENT_FILE = DATA_DIR / "stop_after_current.flag"


def pid_alive(pid):
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
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
            platform TEXT NOT NULL,
            account_id TEXT, action TEXT, status TEXT, detail TEXT, ts TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS target_engagements (
            platform TEXT NOT NULL,
            our_account TEXT, handle TEXT, video_id TEXT,
            liked INTEGER, commented INTEGER, ts TEXT,
            PRIMARY KEY (platform, our_account, handle, video_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS target_follows (
            platform TEXT NOT NULL,
            our_account TEXT, handle TEXT, followed INTEGER, ts TEXT,
            PRIMARY KEY (platform, our_account, handle)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_job_runs (
            job_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            account_id TEXT NOT NULL,
            scheduled_run TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            detail TEXT
        )
    """)
    ensure_platform_column(conn, "action_log")
    ensure_platform_column(conn, "target_engagements")
    ensure_platform_column(conn, "target_follows")
    conn.commit()
    return conn


def table_columns(conn, table_name):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def ensure_platform_column(conn, table_name):
    columns = table_columns(conn, table_name)
    if "platform" not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN platform TEXT")
    conn.execute(
        f"UPDATE {table_name} SET platform=? "
        "WHERE platform IS NULL OR TRIM(platform)=''",
        ("tiktok",),
    )


def require_platform(platform):
    return normalize_platform(platform)


def record_scheduler_job_scheduled(job_id, platform, account_id, scheduled_run):
    platform = require_platform(platform)
    conn = init_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO scheduler_job_runs "
            "(job_id, platform, account_id, scheduled_run, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                job_id,
                platform,
                account_id,
                scheduled_run,
                "pending",
                datetime.now().isoformat(),
            ),
        )
        conn.execute(
            "UPDATE scheduler_job_runs "
            "SET platform=?, account_id=?, scheduled_run=? "
            "WHERE job_id=? AND status='pending'",
            (platform, account_id, scheduled_run, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_scheduler_job_started(job_id, platform, account_id):
    platform = require_platform(platform)
    conn = init_db()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO scheduler_job_runs "
            "(job_id, platform, account_id, status, created_at) VALUES (?,?,?,?,?)",
            (job_id, platform, account_id, "pending", now),
        )
        conn.execute(
            "UPDATE scheduler_job_runs "
            "SET platform=?, account_id=?, status='running', started_at=?, detail=NULL "
            "WHERE job_id=?",
            (platform, account_id, now, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_scheduler_job_finished(job_id, status, detail=""):
    if status not in {"success", "failed", "skipped"}:
        raise ValueError(f"unsupported scheduler job status: {status}")
    conn = init_db()
    try:
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE scheduler_job_runs "
            "SET status=?, ended_at=?, detail=? "
            "WHERE job_id=?",
            (status, now, redact_runtime_text(str(detail or "")), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def has_followed_target(conn, platform, account_id, handle):
    platform = require_platform(platform)
    cur = conn.execute(
        "SELECT followed FROM target_follows WHERE platform=? AND our_account=? AND handle=?",
        (platform, account_id, handle),
    )
    row = cur.fetchone()
    return bool(row and row[0])


def record_target_follow(conn, platform, account_id, handle, followed):
    platform = require_platform(platform)
    conn.execute(
        "INSERT OR REPLACE INTO target_follows (platform, our_account, handle, followed, ts) "
        "VALUES (?,?,?,?,?)",
        (platform, account_id, handle, int(followed), datetime.now().isoformat()),
    )
    conn.commit()


def get_target_watermark(conn, platform, account_id, handle):
    platform = require_platform(platform)
    cur = conn.execute(
        "SELECT video_id FROM target_engagements WHERE platform=? AND our_account=? AND handle=?",
        (platform, account_id, handle),
    )
    ids = [int(r[0]) for r in cur.fetchall() if r[0] and str(r[0]).isdigit()]
    return max(ids) if ids else None


def record_target_engagement(conn, platform, account_id, handle, video_id, liked, commented):
    platform = require_platform(platform)
    conn.execute(
        "INSERT OR REPLACE INTO target_engagements "
        "(platform, our_account, handle, video_id, liked, commented, ts) VALUES (?,?,?,?,?,?,?)",
        (
            platform,
            account_id,
            handle,
            str(video_id),
            int(liked),
            int(commented),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def log_action(conn, platform, account_id, action, status, detail=""):
    platform = require_platform(platform)
    detail = redact_runtime_text(str(detail or ""))
    conn.execute(
        "INSERT INTO action_log (platform, account_id, action, status, detail, ts) VALUES (?,?,?,?,?,?)",
        (platform, account_id, action, status, detail, datetime.now().isoformat()),
    )
    conn.commit()


def session_log(line, platform="tiktok"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = redact_runtime_text(f"{ts} | {require_platform(platform)} | {line}")
    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(full + "\n")
    print(full)


def runtime_redactions():
    values = []
    for key, value in os.environ.items():
        lowered = key.lower()
        if value and (
            "password" in lowered
            or "secret" in lowered
            or "token" in lowered
            or "credential" in lowered
            or "cookie" in lowered
            or ("session" in lowered and lowered != "sessionname")
        ):
            values.append(value)
    return values


def redact_runtime_text(value):
    text = str(value)
    for secret in runtime_redactions():
        if len(secret) >= 3:
            text = text.replace(secret, "***")
    text = PROXY_URL_CREDENTIAL_RE.sub(r"\1***\3", text)
    text = COLON_PROXY_CREDENTIAL_RE.sub(r"\1***", text)
    text = SENSITIVE_KEY_VALUE_RE.sub(r"\1\2***", text)
    return text


def emit_browser_preview(event, account_id, profile_id, cdp_endpoint=None):
    payload = {
        "event": event,
        "account_id": account_id,
        "profile_id": profile_id,
    }
    if cdp_endpoint:
        payload["cdp_endpoint"] = cdp_endpoint
    print(BROWSER_PREVIEW_PREFIX + json.dumps(payload, ensure_ascii=True), flush=True)


def emit_auth_event(account_id, platform, state, detail="", url=None, reason=None):
    payload = {
        "event": "auth_state",
        "account_id": account_id,
        "platform": platform,
        "state": state,
        "detail": detail,
        "intervention_required": state in {"mfa", "captcha", "security_check"},
        "reason": reason or state,
        "checked_at": datetime.now().isoformat(),
    }
    if url:
        payload["url"] = url
    print(AUTH_EVENT_PREFIX + json.dumps(payload, ensure_ascii=True), flush=True)


def auth_intervention_action_dir(account_id):
    safe = "".join(ch if ch.isalnum() or ch in "_-." else "_" for ch in str(account_id).strip())
    safe = safe or "account"
    path = DATA_DIR / "auth_intervention" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_auth_intervention_actions(account_id):
    action_dir = auth_intervention_action_dir(account_id)
    for name in ("continue.flag", "skip.flag", "stop.flag"):
        (action_dir / name).unlink(missing_ok=True)


def wait_for_auth_intervention_action(account_id, poll_seconds=2):
    action_dir = auth_intervention_action_dir(account_id)
    while True:
        if (action_dir / "continue.flag").exists():
            clear_auth_intervention_actions(account_id)
            return "continue"
        if (action_dir / "skip.flag").exists():
            clear_auth_intervention_actions(account_id)
            return "skip"
        if (action_dir / "stop.flag").exists():
            clear_auth_intervention_actions(account_id)
            return "stop"
        time.sleep(poll_seconds)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return load_runtime_config(yaml.safe_load(f))


def load_comment_file(name):
    path = resolve_path(name, base=CONFIG_PATH.parent) or resolve_comments_path(name, CONFIG_PATH)
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def load_comments(config=None, platform="tiktok"):
    cfg = config or load_config()
    platform = require_platform(platform)
    general_file = comments_config(cfg, platform).get("general_file", COMMENTS_PATH.name)
    return load_comment_file(general_file)


def auto_close_profile_enabled():
    return os.environ.get("AM_AUTO_CLOSE_PROFILE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
