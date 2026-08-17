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

FYP_VIDEO_TEXT_LIMITS = {
    "session_id": 128,
    "video_id": 128,
    "video_url": 1000,
    "author_handle": 120,
    "author_name": 200,
    "title": 300,
    "description": 600,
    "capture_status": 32,
    "capture_error": 500,
    "raw_source": 80,
}

PROXY_URL_CREDENTIAL_RE = re.compile(
    r"\b((?:https?|socks5)://[^:\s/@]+:)([^@\s]+)(@[^\s]+)",
    re.IGNORECASE,
)
COLON_PROXY_CREDENTIAL_RE = re.compile(r"(?<!\S)([^:\s]+:\d{1,5}:[^:\s]+:)([^\s]+)")
SENSITIVE_KEY_VALUE_RE = re.compile(
    r"\b(password|passwd|proxy_password|proxy password|api_key|apikey|authorization|credential|credentials|token|cookie|session)\b"
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
    initialize_db_schema(conn)
    return conn


def initialize_db_schema(conn):
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fyp_video_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            account_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            video_index INTEGER NOT NULL,
            video_id TEXT,
            video_url TEXT,
            author_handle TEXT,
            author_name TEXT,
            title TEXT,
            description TEXT,
            watch_seconds REAL,
            liked INTEGER DEFAULT 0,
            followed INTEGER DEFAULT 0,
            commented INTEGER DEFAULT 0,
            capture_status TEXT NOT NULL,
            capture_error TEXT,
            raw_source TEXT,
            collected_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(platform, account_id, session_id, video_index)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fyp_video_views_account_ts
        ON fyp_video_views(platform, account_id, collected_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fyp_video_views_video_id
        ON fyp_video_views(platform, video_id)
    """)
    ensure_platform_column(conn, "action_log")
    ensure_platform_column(conn, "target_engagements")
    ensure_platform_column(conn, "target_follows")
    conn.commit()


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


def record_fyp_video_view(conn, platform, account_id, record):
    """Best-effort insert/update of one FYP video view detail row.

    Returns the stored video_index when the row is written or merged, and False
    when the record cannot be written.
    """
    try:
        platform = require_platform(platform)
        now = datetime.now().isoformat()
        session_id = bounded_fyp_video_text(record.get("session_id"), "session_id")
        video_index = int(record.get("video_index") or 0)
        if not session_id or video_index <= 0:
            raise ValueError("session_id and positive video_index are required")
        collected_at = bounded_fyp_video_text(record.get("collected_at"), "collected_at") or now
        capture_status = (
            bounded_fyp_video_text(record.get("capture_status"), "capture_status") or "partial"
        )
        account_id = str(account_id)
        video_id = bounded_fyp_video_text(record.get("video_id"), "video_id")
        video_url = bounded_fyp_video_text(record.get("video_url"), "video_url")
        author_handle = bounded_fyp_video_text(record.get("author_handle"), "author_handle")
        author_name = bounded_fyp_video_text(record.get("author_name"), "author_name")
        title = bounded_fyp_video_text(record.get("title"), "title")
        description = bounded_fyp_video_text(record.get("description"), "description")
        watch_seconds = normalized_optional_float(record.get("watch_seconds"))
        liked = int(bool(record.get("liked")))
        followed = int(bool(record.get("followed")))
        commented = int(bool(record.get("commented")))
        capture_error = bounded_fyp_video_text(record.get("capture_error"), "capture_error")
        raw_source = bounded_fyp_video_text(record.get("raw_source"), "raw_source")

        duplicate = find_existing_fyp_video_view(
            conn,
            platform,
            account_id,
            session_id,
            video_id,
            video_url,
            author_handle,
            title,
        )
        if duplicate:
            duplicate_id, duplicate_video_index = duplicate
            conn.execute(
                """
                UPDATE fyp_video_views SET
                    video_id=COALESCE(NULLIF(video_id, ''), ?),
                    video_url=COALESCE(NULLIF(video_url, ''), ?),
                    author_handle=COALESCE(NULLIF(author_handle, ''), ?),
                    author_name=COALESCE(NULLIF(author_name, ''), ?),
                    title=COALESCE(NULLIF(title, ''), ?),
                    description=COALESCE(NULLIF(description, ''), ?),
                    watch_seconds=COALESCE(?, watch_seconds),
                    liked=MAX(liked, ?),
                    followed=MAX(followed, ?),
                    commented=MAX(commented, ?),
                    capture_status=CASE
                        WHEN capture_status='ok' THEN capture_status
                        ELSE ?
                    END,
                    capture_error=COALESCE(NULLIF(capture_error, ''), ?),
                    raw_source=COALESCE(NULLIF(raw_source, ''), ?),
                    updated_at=?
                WHERE id=?
                """,
                (
                    video_id,
                    video_url,
                    author_handle,
                    author_name,
                    title,
                    description,
                    watch_seconds,
                    liked,
                    followed,
                    commented,
                    capture_status,
                    capture_error,
                    raw_source,
                    now,
                    duplicate_id,
                ),
            )
            conn.commit()
            return duplicate_video_index

        conn.execute(
            """
            INSERT INTO fyp_video_views (
                platform, account_id, session_id, video_index, video_id, video_url,
                author_handle, author_name, title, description, watch_seconds,
                liked, followed, commented, capture_status, capture_error, raw_source,
                collected_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(platform, account_id, session_id, video_index) DO UPDATE SET
                video_id=excluded.video_id,
                video_url=excluded.video_url,
                author_handle=excluded.author_handle,
                author_name=excluded.author_name,
                title=excluded.title,
                description=excluded.description,
                watch_seconds=excluded.watch_seconds,
                liked=excluded.liked,
                followed=excluded.followed,
                commented=excluded.commented,
                capture_status=excluded.capture_status,
                capture_error=excluded.capture_error,
                raw_source=excluded.raw_source,
                updated_at=excluded.updated_at
            """,
            (
                platform,
                account_id,
                session_id,
                video_index,
                video_id,
                video_url,
                author_handle,
                author_name,
                title,
                description,
                watch_seconds,
                liked,
                followed,
                commented,
                capture_status,
                capture_error,
                raw_source,
                collected_at,
                now,
            ),
        )
        conn.commit()
        return video_index
    except Exception as exc:
        print(f"[warn] fyp video view write skipped: {redact_runtime_text(exc)}")
        return False


def find_existing_fyp_video_view(
    conn,
    platform,
    account_id,
    session_id,
    video_id=None,
    video_url=None,
    author_handle=None,
    title=None,
):
    base = (
        "SELECT id, video_index FROM fyp_video_views "
        "WHERE platform=? AND account_id=? AND session_id=? AND "
    )
    prefix = (platform, account_id, session_id)
    if video_id:
        row = conn.execute(
            base + "video_id=? ORDER BY video_index ASC LIMIT 1",
            (*prefix, video_id),
        ).fetchone()
        if row:
            return row
    if video_url:
        row = conn.execute(
            base + "video_url=? ORDER BY video_index ASC LIMIT 1",
            (*prefix, video_url),
        ).fetchone()
        if row:
            return row
    if title:
        normalized_title = normalize_fyp_video_identity_text(title)
        normalized_author = normalize_fyp_video_identity_text(author_handle)
        row = conn.execute(
            base
            + "LOWER(TRIM(COALESCE(title, '')))=? "
            + "AND LOWER(TRIM(COALESCE(author_handle, '')))=? "
            + "ORDER BY video_index ASC LIMIT 1",
            (*prefix, normalized_title, normalized_author),
        ).fetchone()
        if row:
            return row
    return None


def normalize_fyp_video_identity_text(value):
    return (value or "").strip().lower()


def update_fyp_video_interactions(
    conn,
    platform,
    account_id,
    session_id,
    video_index,
    liked=None,
    followed=None,
    commented=None,
):
    """Best-effort update of interaction flags for one FYP video view row."""
    try:
        platform = require_platform(platform)
        session_id = bounded_fyp_video_text(session_id, "session_id")
        video_index = int(video_index or 0)
        if not session_id or video_index <= 0:
            raise ValueError("session_id and positive video_index are required")

        updates = []
        values = []
        for field, value in (
            ("liked", liked),
            ("followed", followed),
            ("commented", commented),
        ):
            if value is not None:
                updates.append(f"{field}=?")
                values.append(int(bool(value)))
        if not updates:
            return True

        updates.append("updated_at=?")
        values.append(datetime.now().isoformat())
        values.extend([platform, str(account_id), session_id, video_index])
        cur = conn.execute(
            "UPDATE fyp_video_views SET "
            + ", ".join(updates)
            + " WHERE platform=? AND account_id=? AND session_id=? AND video_index=?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        print(f"[warn] fyp video interaction update skipped: {redact_runtime_text(exc)}")
        return False


def bounded_fyp_video_text(value, field):
    if value is None:
        return None
    text = redact_runtime_text(str(value))
    text = "".join(ch if ch >= " " or ch in "\n\t" else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    limit = FYP_VIDEO_TEXT_LIMITS.get(field)
    if limit and len(text) > limit:
        return text[:limit]
    return text


def normalized_optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
            or "api_key" in lowered
            or "apikey" in lowered
            or "authorization" in lowered
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
