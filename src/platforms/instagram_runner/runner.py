"""Instagram platform runner backed by the bridged ins session flow."""
from __future__ import annotations

import time
from typing import Any, Mapping

from browser_providers import provider_for_account
from core import runtime
from platforms.base import PlatformRunner

from .bridge import (
    build_instagram_args,
    create_bitbrowser_client,
    load_ins_modules,
    resolve_bitbrowser_profile,
)


class InstagramRunner(PlatformRunner):
    platform = "instagram"
    executable = True

    def run_session(self, account, config, conn):
        return run_session(account, config, conn)


def run_session(account: Mapping[str, Any], config: Mapping[str, Any], conn):
    provider = provider_for_account(account, config)
    provider.validate_account(account, config)
    if provider.name != "bitbrowser":
        raise ValueError(
            "Instagram warmup runner currently requires the BitBrowser provider"
        )

    modules = load_ins_modules()
    browser_session = modules.browser_session

    account_id = str(account.get("id") or "")
    profile_id = resolve_bitbrowser_profile(account)
    if not profile_id:
        raise ValueError("Instagram account requires a BitBrowser profile id or profile name")

    args = build_instagram_args(account, config)
    bitbrowser = create_bitbrowser_client(config)
    started = time.time()
    summary = {
        "account_id": account_id,
        "platform": "instagram",
        "task_type": "instagram_warmup",
        "status": "unknown",
        "videos": 0,
        "likes": 0,
        "like_failures": 0,
        "follows": 0,
        "comments": 0,
        "target_videos": 0,
        "target_likes": 0,
        "target_comments": 0,
        "target_follows": 0,
        "duration_target_min": float(getattr(args, "duration", 0) or 0),
        "duration_actual_min": 0.0,
        "error": None,
    }

    try:
        stats = browser_session.run_one_profile(
            profile_id,
            bitbrowser,
            conn,
            args,
            account_id=account_id,
        )
    except Exception as exc:
        summary["status"] = "error"
        summary["duration_actual_min"] = round((time.time() - started) / 60, 1)
        summary["error"] = f"Instagram warmup failed: {runtime.redact_runtime_text(exc)}"
        return summary

    summary["duration_actual_min"] = round((time.time() - started) / 60, 1)
    summary["videos"] = int(stats.get("reels", 0) or 0) + int(stats.get("stories", 0) or 0) + int(stats.get("explore", 0) or 0)
    summary["likes"] = int(stats.get("likes", 0) or 0)
    summary["follows"] = int(stats.get("follows", 0) or 0)
    summary["comments"] = int(stats.get("comments", 0) or 0)

    if stats.get("_blocked"):
        summary["status"] = "skip"
        summary["error"] = str(stats.get("_block_detail") or "risk_cooldown")
    elif int(stats.get("errors", 0) or 0) > 0:
        summary["status"] = "error"
        summary["error"] = "Instagram warmup finished with runtime errors"
    else:
        summary["status"] = "ok"

    return summary
