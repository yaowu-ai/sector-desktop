"""Cookie/session persistence helpers for registration tasks."""
from __future__ import annotations

import time
from typing import Any, Mapping

from core import runtime
from platforms.registration.base import RegistrationErrorCode
from platforms.registration.browser_session import RegistrationBrowser


def persist_registration_session(
    page: Any,
    account: Mapping[str, Any],
    config: Mapping[str, Any],
    conn: Any,
    platform: str,
    registration_browser: RegistrationBrowser | None = None,
) -> bool:
    account_id = str(account.get("id") or "")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        page.context.storage_state()
        time.sleep(3)
    except Exception as exc:
        detail = runtime.redact_runtime_text(
            f"{RegistrationErrorCode.SESSION_SAVE_FAILED.value}: {type(exc).__name__}: {exc}"
        )
        runtime.log_action(conn, platform, account_id, "register_error", "error", detail)
        runtime.session_log(f"{account_id} | REGISTER SESSION | error: {detail}", platform)
        raise RuntimeError(RegistrationErrorCode.SESSION_SAVE_FAILED.value) from exc

    detail = session_profile_detail(registration_browser)
    runtime.log_action(conn, platform, account_id, "register_session_saved", "ok", detail)
    runtime.session_log(f"{account_id} | REGISTER SESSION | saved in browser profile; {detail}", platform)
    return True


def session_profile_detail(registration_browser: RegistrationBrowser | None) -> str:
    if registration_browser is None:
        return "provider=unknown; storage=browser_profile"
    session = registration_browser.session
    if session.provider == "builtin_chromium":
        return f"provider={session.provider}; user_data_dir={session.user_data_dir or 'unknown'}"
    if session.provider == "bitbrowser":
        return f"provider={session.provider}; profile_id={session.profile_id or registration_browser.profile_id or 'unknown'}"
    return f"provider={session.provider}; profile_id={session.profile_id or registration_browser.profile_id or 'unknown'}"
