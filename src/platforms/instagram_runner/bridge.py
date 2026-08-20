"""Bridge account-matrix runtime helpers to the standalone ins package."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bitbrowser import BitBrowserClient
from browser_providers import bitbrowser_api_url, bitbrowser_profile_id
from core import runtime
from platform_config import platform_root

ACCOUNT_MATRIX_ROOT = Path(__file__).resolve().parents[3]
INS_SRC_DIR = ACCOUNT_MATRIX_ROOT.parent / "account-matrix-ins" / "src"


@dataclass(frozen=True)
class InsModules:
    storage: Any
    status: Any
    runtime_control: Any
    humanize: Any
    schedule: Any
    schedule_state: Any
    browser_actions: Any
    browser_session: Any


def ensure_ins_source_on_path() -> None:
    try:
        import ins  # noqa: F401
        return
    except ImportError:
        pass
    if not INS_SRC_DIR.exists():
        raise RuntimeError(
            "account-matrix-ins/src is missing; Instagram runner bridge cannot load"
        )
    ins_path = str(INS_SRC_DIR)
    if ins_path not in sys.path:
        sys.path.append(ins_path)


def _append_log_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _instagram_session_log(storage, line: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = runtime.redact_runtime_text(f"[{timestamp}] {line}")
    _append_log_line(runtime.SESSION_LOG, full)
    session_file = getattr(storage, "_SESSION_LOG_FILE", None)
    if session_file:
        session_path = Path(session_file)
        if session_path.resolve() != runtime.SESSION_LOG.resolve():
            _append_log_line(session_path, full)
    print(full)


def _patch_storage_module(storage) -> None:
    storage.ROOT = ACCOUNT_MATRIX_ROOT
    storage.CONFIG_PATH = runtime.CONFIG_PATH
    storage.COMMENTS_PATH = runtime.CONFIG_PATH.parent / "comments.txt"
    storage.DATA_DIR = runtime.DATA_DIR / "ins"
    storage.SESSIONS_DIR = storage.DATA_DIR / "sessions"
    storage.LOG_DB = runtime.LOG_DB
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    storage.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def init_db():
        return runtime.init_db()

    def session_log(line: str) -> None:
        _instagram_session_log(storage, line)

    storage.init_db = init_db
    storage.session_log = session_log
    storage.log_action = runtime.log_ins_action
    storage.compute_remaining_budget = runtime.compute_ins_remaining_budget
    storage.recent_comment_texts = runtime.recent_ins_comment_texts
    storage.get_cooldown_until = runtime.get_ins_cooldown_until
    storage.set_cooldown = runtime.set_ins_cooldown
    storage._record_block_cooldown = runtime.record_ins_block_cooldown


def _patch_status_module(status) -> None:
    status.DEFAULT_STATUS_PATH = runtime.DATA_DIR / "ins" / "status.json"
    status.DEFAULT_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _patch_runtime_control_module(runtime_control) -> None:
    runtime_control.DEFAULT_STOP_PATH = runtime.STOP_AFTER_CURRENT_FILE


def _patch_schedule_state_module(schedule_state) -> None:
    schedule_state.DEFAULT_STATE_PATH = runtime.DATA_DIR / "ins" / "schedule_state.json"
    schedule_state.DEFAULT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    original_save = getattr(
        schedule_state, "_account_matrix_original_save", schedule_state.save
    )
    schedule_state._account_matrix_original_save = original_save

    def save(state, path=None):
        original_save(state, path)
        _mirror_schedule_events_to_runtime_db(state)

    schedule_state.save = save


def _mirror_schedule_events_to_runtime_db(state: Mapping[str, Any] | None) -> None:
    if not isinstance(state, Mapping):
        return
    events = state.get("events")
    if not isinstance(events, list):
        return
    try:
        conn = runtime.init_db()
    except Exception as exc:
        print(f"[warn] Instagram schedule DB mirror skipped: {runtime.redact_runtime_text(exc)}")
        return
    try:
        now = datetime.now().isoformat()
        for event in events:
            if not isinstance(event, Mapping):
                continue
            raw_id = str(event.get("id") or "").strip()
            account_id = str(event.get("account_id") or "").strip()
            scheduled_run = str(event.get("at") or "").strip()
            if not raw_id or not account_id:
                continue
            job_id = f"ins_schedule::{raw_id}"
            conn.execute(
                "INSERT OR IGNORE INTO scheduler_job_runs "
                "(job_id, platform, account_id, scheduled_run, status, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (job_id, "instagram", account_id, scheduled_run, "pending", now),
            )
            status = str(event.get("status") or "pending")
            detail = runtime.redact_runtime_text(str(event.get("detail") or ""))
            if status == "pending":
                conn.execute(
                    "UPDATE scheduler_job_runs "
                    "SET platform=?, account_id=?, scheduled_run=? "
                    "WHERE job_id=? AND status='pending'",
                    ("instagram", account_id, scheduled_run, job_id),
                )
            elif status == "running":
                conn.execute(
                    "UPDATE scheduler_job_runs "
                    "SET platform=?, account_id=?, scheduled_run=?, status='running', "
                    "started_at=COALESCE(started_at, ?), detail=NULL "
                    "WHERE job_id=? AND status NOT IN ('success','failed','skipped')",
                    (
                        "instagram",
                        account_id,
                        scheduled_run,
                        str(event.get("started_at") or now),
                        job_id,
                    ),
                )
            elif status in {"done", "error", "blocked", "skipped", "interrupted", "missed"}:
                mapped_status = {
                    "done": "success",
                    "skipped": "skipped",
                    "missed": "skipped",
                }.get(status, "failed")
                conn.execute(
                    "UPDATE scheduler_job_runs "
                    "SET platform=?, account_id=?, scheduled_run=?, status=?, "
                    "started_at=COALESCE(started_at, ?), ended_at=COALESCE(ended_at, ?), detail=? "
                    "WHERE job_id=? AND status NOT IN ('success','failed','skipped')",
                    (
                        "instagram",
                        account_id,
                        scheduled_run,
                        mapped_status,
                        str(event.get("started_at") or now),
                        str(event.get("finished_at") or now),
                        detail,
                        job_id,
                    ),
                )
        conn.commit()
    except Exception as exc:
        print(f"[warn] Instagram schedule DB mirror skipped: {runtime.redact_runtime_text(exc)}")
    finally:
        conn.close()


def _patch_browser_actions_module(browser_actions, storage) -> None:
    browser_actions._COMMENT_TEMPLATES_PATH = storage.ROOT / "config" / "comments.txt"


def _patch_browser_session_module(browser_session) -> None:
    if not runtime.auto_close_profile_enabled():
        browser_session._close_browser_safe = lambda *args, **kwargs: None


@lru_cache(maxsize=1)
def load_ins_modules() -> InsModules:
    ensure_ins_source_on_path()
    import ins.storage as storage

    _patch_storage_module(storage)

    import ins.status as status
    import ins.runtime_control as runtime_control
    import ins.humanize as humanize
    import ins.schedule as schedule
    import ins.schedule_state as schedule_state
    import ins.browser_actions as browser_actions
    import ins.browser_session as browser_session

    _patch_status_module(status)
    _patch_runtime_control_module(runtime_control)
    _patch_schedule_state_module(schedule_state)
    _patch_browser_actions_module(browser_actions, storage)
    _patch_browser_session_module(browser_session)

    return InsModules(
        storage=storage,
        status=status,
        runtime_control=runtime_control,
        humanize=humanize,
        schedule=schedule,
        schedule_state=schedule_state,
        browser_actions=browser_actions,
        browser_session=browser_session,
    )


def _platform_warmup_config(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    platform_config = platform_root(config, "instagram")
    warmup = platform_config.get("warmup")
    return warmup if isinstance(warmup, Mapping) else {}


def build_instagram_args(account: Mapping[str, Any], config: Mapping[str, Any] | None):
    ensure_ins_source_on_path()
    from ins.config import BUILTIN_DEFAULTS

    defaults = dict(BUILTIN_DEFAULTS)
    warmup = _platform_warmup_config(config)

    api_url = None
    if isinstance(config, Mapping):
        bitbrowser = config.get("bitbrowser")
        if isinstance(bitbrowser, Mapping):
            api_url = bitbrowser.get("api_url")
    if api_url:
        defaults["api_url"] = api_url

    for source in (warmup, account):
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            if key in defaults and value is not None:
                defaults[key] = _coerce_config_value(key, value)

    defaults["force_chaos"] = bool(
        warmup.get("force_chaos")
        if isinstance(warmup, Mapping) and "force_chaos" in warmup
        else account.get("force_chaos") or account.get("chaos")
    )
    defaults["profiles"] = str(account.get("profile") or account.get("id") or "")
    defaults["config"] = runtime.CONFIG_PATH
    defaults["api_url"] = str(defaults.get("api_url") or "http://127.0.0.1:54345")
    defaults["duration"] = _coerce_int(defaults.get("duration"), 15)
    defaults["max_likes_per_day"] = _coerce_int(defaults.get("max_likes_per_day"), 0)
    defaults["max_saves_per_day"] = _coerce_int(defaults.get("max_saves_per_day"), 0)
    defaults["max_follows_per_day"] = _coerce_int(defaults.get("max_follows_per_day"), 0)
    defaults["max_comments_per_day"] = _coerce_int(defaults.get("max_comments_per_day"), 0)
    defaults["max_likes_per_session"] = _coerce_int(
        defaults.get("max_likes_per_session"), 0
    )
    defaults["max_comments_per_session"] = _coerce_int(
        defaults.get("max_comments_per_session"), 1
    )
    defaults["block_cooldown_hours"] = _coerce_float(
        defaults.get("block_cooldown_hours"), 24.0
    )
    for key in (
        "like_prob",
        "save_prob",
        "comment_prob",
    ):
        defaults[key] = _coerce_float(defaults.get(key), 0.0)
    for key in (
        "no_like",
        "no_save",
        "no_comment",
        "no_follow",
        "no_stories",
        "no_reels",
        "no_explore",
        "require_proxy",
        "schedule",
        "loop",
    ):
        defaults[key] = _coerce_bool(defaults.get(key), False)
    return argparse.Namespace(**defaults)


def resolve_bitbrowser_profile(account: Mapping[str, Any]) -> str:
    return bitbrowser_profile_id(account) or str(account.get("profile") or account.get("id") or "")


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_config_value(key: str, value: Any) -> Any:
    if key in {"active_hours"} and isinstance(value, (list, tuple)):
        ranges = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                ranges.append(f"{_format_range_part(item[0])}-{_format_range_part(item[1])}")
        return ",".join(ranges) if ranges else value
    if key in {"gap", "loop_interval", "sessions_per_day", "duration_jitter"}:
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return f"{value[0]}-{value[1]}"
    return value


def _format_range_part(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric)


def create_bitbrowser_client(config: Mapping[str, Any] | None):
    return BitBrowserClient(bitbrowser_api_url(config or {}))
