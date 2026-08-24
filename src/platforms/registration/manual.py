"""Manual intervention helpers for registration tasks."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from core import runtime


def require_manual_intervention(
    account: Mapping[str, Any],
    platform: str,
    state: str,
    reason: str,
    detail: str,
    page: Optional[Any] = None,
) -> None:
    account_id = str(account.get("id") or "")
    url = getattr(page, "url", None) if page is not None else None
    runtime.emit_auth_event(account_id, platform, state, detail, url=url, reason=reason)
    runtime.session_log(
        f"{account_id} | REGISTER MANUAL | state={state}; reason={reason}; {detail}",
        platform,
    )


def wait_for_manual_intervention(account: Mapping[str, Any]) -> str:
    return runtime.wait_for_auth_intervention_action(str(account.get("id") or ""))
