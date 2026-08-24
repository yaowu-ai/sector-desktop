"""Browser helpers shared by registration adapters."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

from browser_providers import (
    BrowserSession,
    bitbrowser_profile_id,
    provider_for_account,
    test_cdp_endpoint,
)
from core import runtime


@dataclass
class RegistrationBrowser:
    provider: Any
    session: BrowserSession
    profile_id: Optional[str]


def validate_registration_browser(account: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    provider = provider_for_account(account, config)
    provider.validate_account(account, config)


@contextmanager
def open_registration_browser(
    account: Mapping[str, Any],
    config: Mapping[str, Any],
    platform: str,
) -> Iterator[RegistrationBrowser]:
    account_id = str(account.get("id") or "")
    provider = provider_for_account(account, config)
    provider.validate_account(account, config)
    profile_id = bitbrowser_profile_id(account) or account_id

    runtime.session_log(f"{account_id} | REGISTER OPEN | provider={provider.name}", platform)
    session = provider.start_session(account, config)
    runtime.emit_browser_preview("opened", account_id, session.profile_id or profile_id, session.cdp_endpoint)
    test_cdp_endpoint(session.cdp_endpoint, timeout=5)

    try:
        yield RegistrationBrowser(provider=provider, session=session, profile_id=profile_id)
    finally:
        pass


def close_registration_browser(
    browser: RegistrationBrowser,
    config: Mapping[str, Any],
    platform: str,
    account_id: str,
    conn: Any = None,
) -> bool | None:
    if browser.session.already_open:
        detail = f"provider={browser.provider.name}; already_open=true; left open"
        runtime.session_log(f"{account_id} | REGISTER CLOSE | skip: {detail}", platform)
        if conn is not None:
            runtime.log_action(conn, platform, account_id, "register_browser_closed", "skip", detail)
        return None

    try:
        close_result = browser.provider.close_session(browser.session, config)
    except Exception as exc:
        detail = runtime.redact_runtime_text(
            f"REGISTER_BROWSER_CLOSE_FAILED: provider={browser.provider.name}; error={type(exc).__name__}: {exc}"
        )
        runtime.session_log(f"{account_id} | REGISTER CLOSE | error: {detail}", platform)
        if conn is not None:
            runtime.log_action(conn, platform, account_id, "register_error", "error", detail)
        return False

    if close_result is None:
        detail = f"provider={browser.provider.name}"
        status = "ok"
    else:
        detail = runtime.redact_runtime_text(getattr(close_result, "detail", str(close_result)))
        status = str(getattr(close_result, "status", "ok") or "ok")

    success = status in {"ok", "closed", "already_exited", "closed_residual", "no_pid"}
    runtime.session_log(f"{account_id} | REGISTER CLOSE | {status}: {detail}", platform)
    if success:
        runtime.emit_browser_preview("closed", account_id, browser.session.profile_id or browser.profile_id)
        if conn is not None:
            runtime.log_action(conn, platform, account_id, "register_browser_closed", "ok", detail)
    elif conn is not None:
        runtime.log_action(
            conn,
            platform,
            account_id,
            "register_error",
            "error",
            f"REGISTER_BROWSER_CLOSE_FAILED: {detail}",
        )
    return success
