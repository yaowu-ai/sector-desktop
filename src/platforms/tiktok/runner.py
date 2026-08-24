"""TikTok platform runner."""
import os
import time

from auth_adapters import LoginState, auth_adapter_for_platform
from browser_providers import (
    bitbrowser_profile_id,
    provider_for_account,
    test_cdp_endpoint,
)
from core.runtime import (
    auto_close_profile_enabled,
    clear_auth_intervention_actions,
    emit_browser_preview,
    emit_auth_event,
    log_action,
    redact_runtime_text,
    session_log,
    wait_for_auth_intervention_action,
)
from patchright_runtime import start_sync_playwright
from platforms.base import PlatformRunner
from platforms.registration.base import RegistrationStatus
from platforms.registration.registry import adapter_for_platform
from platforms.tiktok.auth import TikTokAuthAdapter, auto_login_enabled
from platforms.tiktok.fyp import build_fyp_plan, run_tiktok_fyp
from platforms.tiktok.register import ensure_tiktok_google_login
from platforms.tiktok.target import run_target_engagement


class TikTokRunner(PlatformRunner):
    platform = "tiktok"
    executable = True

    def run_session(self, account, config, conn):
        return run_session(account, config, conn)


def classify_tiktok_network_error(exc):
    text = f"{type(exc).__name__}: {exc}".lower()
    for category in ("proxy_failed", "connection_reset", "timeout", "dns", "network_error"):
        if f"category={category}" in text:
            return category
    if "err_proxy_connection_failed" in text or "proxy" in text or "tunnel" in text or "socks" in text:
        return "proxy_failed"
    if "err_connection_reset" in text or "connection reset" in text:
        return "connection_reset"
    if (
        "err_name_not_resolved" in text
        or "dns" in text
        or "name or service not known" in text
        or "nodename nor servname" in text
        or "getaddrinfo" in text
    ):
        return "dns"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "net::err_" in text or "navigation failed" in text:
        return "network_error"
    return None


def tiktok_network_error_detail(exc, action="navigation"):
    detail = redact_runtime_text(f"{type(exc).__name__}: {exc}")
    category = classify_tiktok_network_error(exc)
    if category:
        return f"TikTok {action} failed: category={category}; detail={detail}"
    return f"TikTok {action} failed: detail={detail}"


def requested_tiktok_task():
    value = os.environ.get("AM_TASK_TYPE", "").strip().lower()
    aliases = {
        "warmup": "fyp",
        "target": "target_engagement",
        "register": "tiktok_register",
        "registration": "tiktok_register",
    }
    value = aliases.get(value, value)
    if value in {"fyp", "target_engagement", "tiktok_register", "full"}:
        return value
    return "full"


def choose_tiktok_page(context):
    fallback = None
    for page in context.pages:
        url = page.url or ""
        if "tiktok.com" in url:
            page.bring_to_front()
            return page
        if fallback is None and "console.bitbrowser.net" not in url:
            fallback = page

    page = fallback or (context.pages[0] if context.pages else context.new_page())
    try:
        page.goto("https://www.tiktok.com/foryou", timeout=60000)
    except Exception as exc:
        raise RuntimeError(tiktok_network_error_detail(exc)) from exc
    page.bring_to_front()
    return page


def _legacy_visible_count(page, selector, timeout=800):
    try:
        locator = page.locator(selector)
        count = locator.count()
        visible = 0
        for index in range(min(count, 5)):
            if locator.nth(index).is_visible(timeout=timeout):
                visible += 1
        return visible
    except Exception:
        return 0


def _legacy_detect_login_state(page):
    """Return (is_logged_in, detail) for the current TikTok page."""
    try:
        page.goto("https://www.tiktok.com/foryou", timeout=60000)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        time.sleep(3)
    except Exception as exc:
        return False, tiktok_network_error_detail(exc)

    url = page.url or ""
    if any(marker in url.lower() for marker in ("/login", "login?")):
        return False, f"redirected to login page: {url}"

    logged_in_markers = [
        '[data-e2e="profile-icon"]',
        '[data-e2e="nav-profile"]',
        'a[href*="/upload"]',
        'button[aria-label*="Like" i]',
        '[data-e2e="feed-follow"]',
        '[data-e2e="comment-icon"]',
    ]
    login_markers = [
        '[data-e2e="top-login-button"]',
        '[data-e2e="login-button"]',
        'button:has-text("Log in")',
        'button:has-text("登录")',
        'button:has-text("登入")',
        'text=/Log in to TikTok/i',
        'text=/Sign up for TikTok/i',
        'text=/登录 TikTok/i',
    ]

    logged_in_hits = sum(_legacy_visible_count(page, selector) for selector in logged_in_markers)
    login_hits = sum(_legacy_visible_count(page, selector) for selector in login_markers)

    if login_hits and not logged_in_hits:
        return False, "login prompt detected"
    if logged_in_hits:
        return True, f"interactive TikTok controls detected ({logged_in_hits})"

    try:
        title = page.title(timeout=1000)
    except Exception:
        title = ""
    return False, f"unable to confirm login state; url={url}; title={title}"


def detect_login_state(page):
    """Compatibility wrapper returning (is_logged_in, detail)."""
    result = TikTokAuthAdapter().ensure_logged_in(page, {}, {})
    return result.logged_in, result.summary()


def ensure_tiktok_authenticated(page, account, config, conn):
    account_id = account["id"]
    platform = account.get("platform", "tiktok")
    adapter = auth_adapter_for_platform(platform)
    clear_auth_intervention_actions(account_id)

    while True:
        auth_result = adapter.ensure_logged_in(page, account, config)
        detail = auth_result.summary()
        emit_auth_event(
            account_id,
            platform,
            auth_result.state.value,
            auth_result.detail,
            url=auth_result.url,
            reason=auth_result.intervention.reason if auth_result.intervention else auth_result.state.value,
        )
        if auth_result.state == LoginState.LOGGED_IN:
            log_action(conn, platform, account_id, "login_check", "ok", detail)
            return auth_result

        log_action(conn, platform, account_id, "login_check", auth_result.state.value, detail)
        if (
            auth_result.state in {LoginState.LOGIN_PAGE, LoginState.LOGGED_OUT}
            and auto_login_enabled(account)
            and auth_result.error_code != "AUTH_TIKTOK_CREDENTIAL_MISSING"
        ):
            session_log(
                f"{account_id} | AUTH GOOGLE | login page detected; trying Google login recovery",
                platform,
            )
            auth_result = ensure_tiktok_google_login(page, account, config, conn, platform)
            detail = auth_result.summary()
            emit_auth_event(
                account_id,
                platform,
                auth_result.state.value,
                auth_result.detail,
                url=auth_result.url,
                reason=auth_result.intervention.reason if auth_result.intervention else auth_result.state.value,
            )
            log_action(conn, platform, account_id, "login_check", auth_result.state.value, detail)
            return auth_result
        if auth_result.state not in {
            LoginState.MFA,
            LoginState.CAPTCHA,
            LoginState.SECURITY_CHECK,
        }:
            return auth_result

        session_log(
            f"{account_id} | AUTH WAIT | state={auth_result.state.value}; manual intervention required",
            platform,
        )
        action = wait_for_auth_intervention_action(account_id)
        if action == "continue":
            session_log(f"{account_id} | AUTH CONTINUE | rechecking login state", platform)
            continue
        if action == "skip":
            session_log(f"{account_id} | AUTH SKIP | user skipped current account", platform)
            return auth_result
        raise RuntimeError("stopped by user during auth intervention")


def run_session(account, config, conn):
    account_id = account["id"]
    platform = account.get("platform", "tiktok")
    task_type = requested_tiktok_task()
    if task_type == "tiktok_register":
        return run_tiktok_registration(account, config, conn)

    plan = build_fyp_plan(account, config) if task_type in {"fyp", "full"} else None
    duration = plan["duration"] if plan else 0.0

    summary = {
        "account_id": account_id,
        "platform": platform,
        "task_type": task_type,
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
        "duration_target_min": round(duration, 1),
        "duration_actual_min": 0.0,
        "error": None,
    }

    provider = provider_for_account(account, config)
    provider.validate_account(account, config)
    profile_id = bitbrowser_profile_id(account)

    if provider.is_open(account, config):
        session_log(f"{account_id} | SKIP | profile already open", platform)
        log_action(conn, platform, account_id, "session", "skip", "profile already open")
        summary["status"] = "skip"
        return summary

    session_log(
        start_session_detail(account_id, task_type, plan, provider.name),
        platform,
    )
    log_action(conn, platform, account_id, "open", "start", f"provider={provider.name}")

    started = time.time()
    session = None
    try:
        session = provider.start_session(account, config)
        cdp_url = session.cdp_endpoint
        emit_browser_preview("opened", account_id, session.profile_id, cdp_url)
        time.sleep(3)
        test_cdp_endpoint(cdp_url, timeout=5)

        playwright_manager, playwright = start_sync_playwright()
        try:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = choose_tiktok_page(ctx)

            auth_result = ensure_tiktok_authenticated(page, account, config, conn)
            login_detail = auth_result.summary()
            if auth_result.state != LoginState.LOGGED_IN:
                summary["status"] = "skip"
                summary["error"] = login_detail
                session_log(
                    f"{account_id} | SKIP | TikTok auth state={auth_result.state.value}: {auth_result.detail}",
                    platform,
                )
                browser.close()
                return summary

            if task_type in {"fyp", "full"}:
                fyp = run_tiktok_fyp(page, account, plan, conn)
                summary.update(fyp)

            if task_type in {"target_engagement", "full"}:
                target = run_target_engagement(page, account, config, conn)
                summary["target_videos"] = target["videos"]
                summary["target_likes"] = target["likes"]
                summary["like_failures"] += target.get("like_failures", 0)
                summary["target_comments"] = target["comments"]
                summary["target_follows"] = target["follows"]

            summary["status"] = "ok"

            browser.close()
        finally:
            playwright_manager.__exit__()
        actual = (time.time() - started) / 60
        summary["duration_actual_min"] = round(actual, 1)
        session_log(
            f"{account_id} | OK | {summary['videos']}v / {summary['likes']}L / "
            f"{summary['like_failures']}LF / {summary['follows']}F / {summary['comments']}C "
            f"(+target {summary['target_videos']}v/{summary['target_likes']}L/"
            f"{summary['target_comments']}C) in {actual:.1f}min",
            platform,
        )
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = tiktok_network_error_detail(exc, action="session")
        log_action(conn, platform, account_id, "session", "error", summary["error"])
        session_log(f"{account_id} | ERROR | {summary['error']}", platform)
    finally:
        if auto_close_profile_enabled():
            if session is not None:
                close_result = provider.close_session(session, config)
                if close_result is not None:
                    detail = getattr(close_result, "detail", str(close_result))
                    status = getattr(close_result, "status", "ok")
                    session_log(f"{account_id} | CLOSE | {status}: {detail}", platform)
            emit_browser_preview("closed", account_id, profile_id)
            log_action(conn, platform, account_id, "close", "ok")
        else:
            session_log(f"{account_id} | CLOSE SKIP | AM_AUTO_CLOSE_PROFILE=0", platform)

    return summary


def run_tiktok_registration(account, config, conn):
    account_id = account["id"]
    platform = account.get("platform", "tiktok")
    started = time.time()
    summary = {
        "account_id": account_id,
        "platform": platform,
        "task_type": "tiktok_register",
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
        "duration_target_min": 0.0,
        "duration_actual_min": 0.0,
        "error": None,
        "registered_username": None,
    }
    adapter = adapter_for_platform(platform)
    log_action(conn, platform, account_id, "register_auto_start", "start", "task_type=tiktok_register")
    session_log(f"{account_id} | REGISTER AUTO START | task=tiktok_register", platform)
    result = adapter.register(account, config, conn)
    summary["duration_actual_min"] = round((time.time() - started) / 60, 1)
    summary["registered_username"] = result.username
    if result.status == RegistrationStatus.COMPLETE:
        summary["status"] = "ok"
        log_action(
            conn,
            platform,
            account_id,
            "login_check",
            LoginState.LOGGED_IN.value,
            "registration completed and browser session saved",
        )
        log_action(
            conn,
            platform,
            account_id,
            "register_auto_complete",
            "ok",
            result.summary(),
        )
    elif result.status == RegistrationStatus.MANUAL_REQUIRED:
        summary["status"] = "skip"
        summary["error"] = result.summary()
        log_action(
            conn,
            platform,
            account_id,
            "register_auto_manual_required",
            "skip",
            result.summary(),
        )
    else:
        summary["status"] = "error"
        summary["error"] = result.summary()
        log_action(
            conn,
            platform,
            account_id,
            "register_auto_failed",
            "error",
            result.summary(),
        )
    session_log(
        f"{account_id} | REGISTER RESULT | {result.summary()}",
        platform,
    )
    return summary


def start_session_detail(account_id, task_type, plan, provider):
    if plan:
        return (
            f"{account_id} | START | task={task_type} provider={provider} target={plan['duration']:.1f}min "
            f"like_p={plan['like_prob']} follows_max={plan['follows_target']} "
            f"comments_max={plan['comments_target']}"
        )
    return f"{account_id} | START | task={task_type} provider={provider}"
