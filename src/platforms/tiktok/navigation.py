"""Shared TikTok navigation with bounded network retries."""
from __future__ import annotations

import time
from typing import Any


TIKTOK_FORYOU_URL = "https://www.tiktok.com/foryou"
TIKTOK_NAVIGATION_TIMEOUT_MS = 30_000
TIKTOK_NAVIGATION_MAX_RETRIES = 3
TIKTOK_POST_LOAD_WAIT_SECONDS = 15


def is_retryable_tiktok_navigation_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        marker in text
        for marker in (
            "timeout",
            "timed out",
            "err_socks_connection_failed",
            "err_proxy_connection_failed",
            "err_connection_reset",
            "connection reset",
            "proxy",
            "socks",
            "tunnel",
            "net::err_",
            "navigation failed",
        )
    )


def navigate_tiktok_page(
    page: Any,
    *,
    wait_for_domcontentloaded: bool = False,
    post_load_wait_seconds: float = 0,
) -> Any:
    """Navigate to TikTok, retrying only transient network failures."""
    attempts = TIKTOK_NAVIGATION_MAX_RETRIES + 1
    last_error: BaseException | None = None

    for attempt in range(attempts):
        try:
            page.goto(
                TIKTOK_FORYOU_URL,
                timeout=TIKTOK_NAVIGATION_TIMEOUT_MS,
            )
            if wait_for_domcontentloaded:
                page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=TIKTOK_NAVIGATION_TIMEOUT_MS,
                )
            if post_load_wait_seconds:
                time.sleep(post_load_wait_seconds)
            return page
        except Exception as exc:
            last_error = exc
            if attempt >= TIKTOK_NAVIGATION_MAX_RETRIES or not is_retryable_tiktok_navigation_error(exc):
                raise

    raise RuntimeError("TikTok navigation failed without an error") from last_error
