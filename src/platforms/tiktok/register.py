"""TikTok Google registration adapter."""
from __future__ import annotations

import time
from typing import Any, Mapping

from core import runtime
from patchright_runtime import start_sync_playwright, stop_sync_playwright
from platforms.registration.base import (
    RegistrationAdapter,
    RegistrationErrorCode,
    RegistrationResult,
    RegistrationStatus,
)
from platforms.registration.browser_session import (
    close_registration_browser,
    open_registration_browser,
)
from platforms.registration.credentials import read_registration_credentials
from platforms.registration.cookies import persist_registration_session
from platforms.registration.manual import require_manual_intervention, wait_for_manual_intervention
from platforms.registration.random_identity import (
    generate_unique_username,
    random_birthday,
    record_username,
)
from platforms.tiktok.auth import classify_tiktok_page, click_tiktok_google_one_tap


TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"

CONTINUE_WITH_GOOGLE_SELECTORS = [
    'button:has-text("Continue with Google")',
    '[role="button"]:has-text("Continue with Google")',
    'text=/Continue with Google/i',
    'button:has-text("\u4f7f\u7528 Google \u767b\u5f55")',
    '[role="button"]:has-text("\u4f7f\u7528 Google \u767b\u5f55")',
    'text=/\u4f7f\u7528\\s*Google\\s*\u767b\u5f55/i',
]

BIRTHDAY_SELECTORS = {
    "page": 'text=/When\\\'s your birthday/i',
    "month": '[role="combobox"]:has-text("Month"), select:has(option:has-text("Month"))',
    "day": '[role="combobox"]:has-text("Day"), select:has(option:has-text("Day"))',
    "year": '[role="combobox"]:has-text("Year"), select:has(option:has-text("Year"))',
    "next": 'button:has-text("Next")',
}

USERNAME_SELECTORS = {
    "input": 'input[name="username"], input[placeholder*="Username" i], input[autocomplete="username"]',
    "submit": 'button:has-text("Sign up")',
}

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

USERNAME_UNAVAILABLE_PATTERNS = [
    "username isn't available",
    "username is not available",
    "username unavailable",
    "already taken",
    "try another",
    "not available",
    "用户名不可用",
    "已被使用",
]

TIKTOK_INTEREST_SELECTORS = [
    'button:has-text("Travel")',
    '[role="button"]:has-text("Travel")',
    'button:has-text("Food")',
    '[role="button"]:has-text("Food")',
    'button:has-text("Art")',
    '[role="button"]:has-text("Art")',
    'button:has-text("Gaming")',
    '[role="button"]:has-text("Gaming")',
    'button:has-text("Animals")',
    '[role="button"]:has-text("Animals")',
    'button:has-text("Comedy")',
    '[role="button"]:has-text("Comedy")',
]

TIKTOK_INTEREST_CONTINUE_SELECTORS = [
    'button:has-text("Continue")',
    '[role="button"]:has-text("Continue")',
]

GOOGLE_EMAIL_SELECTORS = [
    'input[type="email"]',
    'input[autocomplete="username"]',
    'input[aria-label*="Email" i]',
    'input[aria-label*="phone" i]',
    'input[aria-label*="\u90ae\u7bb1"]',
    'input[aria-label*="\u7535\u8bdd\u53f7\u7801"]',
    'input[placeholder*="\u90ae\u7bb1"]',
    'input[placeholder*="\u7535\u8bdd\u53f7\u7801"]',
    'input[name="identifier"]',
]

GOOGLE_PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    'input[aria-label*="password" i]',
    'input[aria-label*="\u5bc6\u7801"]',
    'input[placeholder*="\u5bc6\u7801"]',
    'input[name="Passwd"]',
]

GOOGLE_NEXT_SELECTORS = [
    'button:has-text("Next")',
    '[role="button"]:has-text("Next")',
    'button:has-text("\u4e0b\u4e00\u6b65")',
    '[role="button"]:has-text("\u4e0b\u4e00\u6b65")',
    'text=/^\u4e0b\u4e00\u6b65$/',
    '#identifierNext button',
    '#passwordNext button',
]

GOOGLE_ACCOUNT_CHOOSER_SELECTORS = [
    '[data-identifier][role="link"]',
    '[data-identifier]',
    '[role="link"]:has([data-identifier])',
    '[role="button"]:has-text("@")',
]

GOOGLE_CHALLENGE_PATTERNS = {
    "google_captcha": [
        "captcha",
        "verify you are human",
        "unusual traffic",
        "prove you're not a robot",
    ],
    "google_mfa": [
        "2-step verification",
        "two-step verification",
        "verification code",
        "get a verification code",
        "check your phone",
        "authenticator",
    ],
    "google_security_check": [
        "verify it's you",
        "confirm your identity",
        "security check",
        "this device isn't recognized",
        "suspicious",
    ],
}

GOOGLE_LOGIN_MAX_ATTEMPTS = 3
LOGIN_PROMPT_RETRY_SECONDS = 15


class TikTokGoogleRegistrationAdapter:
    platform = "tiktok"

    def register(
        self,
        account: Mapping[str, Any],
        config: Mapping[str, Any],
        conn: Any,
    ) -> RegistrationResult:
        account_id = str(account.get("id") or "")
        runtime.clear_auth_intervention_actions(account_id)
        credentials = read_registration_credentials(account)
        planned_birthday = random_birthday()
        planned_username = generate_unique_username(self.platform)

        runtime.log_action(conn, self.platform, account_id, "register_open", "start", "task_type=tiktok_register")
        try:
            with open_registration_browser(account, config, self.platform) as registration_browser:
                try:
                    playwright_manager, playwright = start_sync_playwright()
                    try:
                        browser = playwright.chromium.connect_over_cdp(
                            registration_browser.session.cdp_endpoint
                        )
                        context = browser.contexts[0] if browser.contexts else browser.new_context()
                        page = choose_tiktok_registration_page(context)
                        open_tiktok_login_page(page)
                        runtime.log_action(
                            conn,
                            self.platform,
                            account_id,
                            "register_open_login",
                            "ok",
                            f"url={getattr(page, 'url', '')}",
                        )
                        google_page, google_result, _ = run_google_login_from_tiktok_login_page(
                            page,
                            account,
                            credentials,
                            conn,
                            self.platform,
                        )
                        if google_result is not None:
                            return finish_intermediate_registration_result(
                                google_result,
                                registration_browser,
                                config,
                                conn,
                                self.platform,
                            )
                        planned_username, signup_result = run_tiktok_signup_steps(
                            page,
                            account,
                            conn,
                            self.platform,
                            planned_birthday,
                            planned_username,
                        )
                        if signup_result is not None:
                            return finish_intermediate_registration_result(
                                signup_result,
                                registration_browser,
                                config,
                                conn,
                                self.platform,
                            )
                        google_page, google_result, retried_login = run_google_login_from_tiktok_login_page(
                            page,
                            account,
                            credentials,
                            conn,
                            self.platform,
                        )
                        if google_result is not None:
                            return finish_intermediate_registration_result(
                                google_result,
                                registration_browser,
                                config,
                                conn,
                                self.platform,
                            )
                        if retried_login:
                            planned_username, signup_result = run_tiktok_signup_steps(
                                page,
                                account,
                                conn,
                                self.platform,
                                planned_birthday,
                                planned_username,
                            )
                            if signup_result is not None:
                                return finish_intermediate_registration_result(
                                    signup_result,
                                    registration_browser,
                                    config,
                                    conn,
                                    self.platform,
                                )
                        completed = detect_registration_complete(page, account_id)
                        if completed:
                            return complete_registration_result(
                                page,
                                registration_browser,
                                account,
                                config,
                                conn,
                                self.platform,
                                planned_username,
                                "TikTok registration completed and session saved",
                            )
                        detail = (
                            "TikTok registration opened Google flow and is waiting for manual completion; "
                            f"credential_username={'set' if credentials.username else 'missing'}; "
                            f"birthday_year={planned_birthday['year']}; username_length={len(planned_username)}; "
                            f"google_url={getattr(google_page, 'url', '')}"
                        )
                        require_manual_intervention(
                            account,
                            self.platform,
                            "security_check",
                            "registration_google_flow_pending",
                            detail,
                            page,
                        )
                        runtime.log_action(
                            conn,
                            self.platform,
                            account_id,
                            "register_manual_required",
                            "pending",
                            "registration_google_flow_pending",
                        )
                        action = wait_for_manual_intervention(account)
                        if action == "continue":
                            planned_username, signup_result = run_tiktok_signup_steps(
                                page,
                                account,
                                conn,
                                self.platform,
                                planned_birthday,
                                planned_username,
                            )
                            if signup_result is not None:
                                return finish_intermediate_registration_result(
                                    signup_result,
                                    registration_browser,
                                    config,
                                    conn,
                                    self.platform,
                                )
                            google_page, google_result, retried_login = run_google_login_from_tiktok_login_page(
                                page,
                                account,
                                credentials,
                                conn,
                                self.platform,
                            )
                            if google_result is not None:
                                return finish_intermediate_registration_result(
                                    google_result,
                                    registration_browser,
                                    config,
                                    conn,
                                    self.platform,
                                )
                            if retried_login:
                                planned_username, signup_result = run_tiktok_signup_steps(
                                    page,
                                    account,
                                    conn,
                                    self.platform,
                                    planned_birthday,
                                    planned_username,
                                )
                                if signup_result is not None:
                                    return finish_intermediate_registration_result(
                                        signup_result,
                                        registration_browser,
                                        config,
                                        conn,
                                        self.platform,
                                    )
                            if detect_registration_complete(page, account_id):
                                return complete_registration_result(
                                    page,
                                    registration_browser,
                                    account,
                                    config,
                                    conn,
                                    self.platform,
                                    planned_username,
                                    "TikTok registration completed after manual intervention",
                                )
                            detail = "manual intervention continued, but TikTok login state is not complete yet"
                        elif action == "skip":
                            detail = "user skipped registration after manual intervention"
                        else:
                            raise RuntimeError("stopped by user during registration intervention")
                        return RegistrationResult(
                            platform=self.platform,
                            account_id=account_id,
                            status=RegistrationStatus.MANUAL_REQUIRED,
                            detail=detail,
                            error_code=RegistrationErrorCode.MANUAL_INTERVENTION_REQUIRED,
                            username=planned_username,
                            manual_reason="registration_google_flow_pending",
                        )
                    finally:
                        cleanup_error = stop_sync_playwright(playwright_manager)
                        if cleanup_error:
                            cleanup_detail = runtime.redact_runtime_text(
                                f"Patchright cleanup failed: {cleanup_error}"
                            )
                            runtime.session_log(
                                f"{account_id} | REGISTER RUNTIME CLEANUP | warning: {cleanup_detail}",
                                self.platform,
                            )
                            runtime.log_action(
                                conn,
                                self.platform,
                                account_id,
                                "register_runtime_cleanup",
                                "warning",
                                cleanup_detail,
                            )
                except Exception as exc:
                    detail = registration_network_error_detail(exc)
                    error_code = registration_error_code_for_exception(
                        exc,
                        RegistrationErrorCode.TIKTOK_LOGIN_LOAD_FAILED,
                    )
                    runtime.log_action(
                        conn,
                        self.platform,
                        account_id,
                        "register_error",
                        "error",
                        f"{error_code.value}: {detail}",
                    )
                    close_registration_browser(
                        registration_browser,
                        config,
                        self.platform,
                        account_id,
                        conn,
                    )
                    return RegistrationResult(
                        platform=self.platform,
                        account_id=account_id,
                        status=RegistrationStatus.ERROR,
                        detail=detail,
                        error_code=error_code,
                    )
        except Exception as exc:
            detail = registration_network_error_detail(exc, action="browser open")
            runtime.log_action(
                conn,
                self.platform,
                account_id,
                "register_error",
                "error",
                f"{RegistrationErrorCode.BROWSER_OPEN_FAILED.value}: {detail}",
            )
            return RegistrationResult(
                platform=self.platform,
                account_id=account_id,
                status=RegistrationStatus.ERROR,
                detail=detail,
                error_code=RegistrationErrorCode.BROWSER_OPEN_FAILED,
            )


def choose_tiktok_registration_page(context: Any):
    fallback = None
    for page in context.pages:
        url = page.url or ""
        if "tiktok.com" in url:
            page.bring_to_front()
            return page
        if fallback is None and "console.bitbrowser.net" not in url:
            fallback = page
    page = fallback or (context.pages[0] if context.pages else context.new_page())
    page.bring_to_front()
    return page


def finish_intermediate_registration_result(
    result: RegistrationResult,
    registration_browser: Any,
    config: Mapping[str, Any],
    conn: Any,
    platform: str,
) -> RegistrationResult:
    if result.status == RegistrationStatus.MANUAL_REQUIRED:
        return result
    if result.status == RegistrationStatus.ERROR:
        log_registration_error(conn, platform, result.account_id, result.detail, result.error_code)
    close_registration_browser(
        registration_browser,
        config,
        platform,
        result.account_id,
        conn,
    )
    return result


def complete_registration_result(
    page: Any,
    registration_browser: Any,
    account: Mapping[str, Any],
    config: Mapping[str, Any],
    conn: Any,
    platform: str,
    username: str,
    detail: str,
) -> RegistrationResult:
    account_id = str(account.get("id") or "")
    finalize_tiktok_registration_session(page, account, conn, platform)
    if not detect_registration_complete(page, account_id):
        error_detail = "TikTok login state was not confirmed before session save"
        log_registration_error(
            conn,
            platform,
            account_id,
            error_detail,
            RegistrationErrorCode.SESSION_SAVE_FAILED,
        )
        close_registration_browser(registration_browser, config, platform, account_id, conn)
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail=error_detail,
            error_code=RegistrationErrorCode.SESSION_SAVE_FAILED,
            username=username,
        )

    try:
        persist_registration_session(page, account, config, conn, platform, registration_browser)
    except Exception as exc:
        close_registration_browser(registration_browser, config, platform, account_id, conn)
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail=registration_network_error_detail(exc, action="session save"),
            error_code=RegistrationErrorCode.SESSION_SAVE_FAILED,
            username=username,
        )

    close_status = close_registration_browser(registration_browser, config, platform, account_id, conn)
    browser_closed = close_status is True
    if close_status is True:
        result_detail = detail
        complete_detail = "browser_closed=true"
    elif close_status is None:
        result_detail = f"{detail}; browser was already open and left open"
        complete_detail = "browser_closed=false; close_skipped=already_open"
    else:
        result_detail = f"{detail}; browser close failed"
        complete_detail = "browser_closed=false"
    runtime.log_action(
        conn,
        platform,
        account_id,
        "register_complete",
        "ok",
        complete_detail,
    )
    return RegistrationResult(
        platform=platform,
        account_id=account_id,
        status=RegistrationStatus.COMPLETE,
        detail=result_detail,
        username=username,
        browser_closed=browser_closed,
    )


def log_registration_error(
    conn: Any,
    platform: str,
    account_id: str,
    detail: str,
    error_code: RegistrationErrorCode | None,
) -> None:
    prefix = error_code.value if error_code else "REGISTER_ERROR"
    runtime.log_action(conn, platform, account_id, "register_error", "error", f"{prefix}: {detail}")


def open_tiktok_login_page(page: Any) -> None:
    try:
        page.goto(TIKTOK_LOGIN_URL, timeout=60000)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception as exc:
        raise RuntimeError(registration_network_error_detail(exc, action="login load")) from exc


def click_continue_with_google(page: Any) -> None:
    for selector in CONTINUE_WITH_GOOGLE_SELECTORS:
        try:
            locator = page.locator(selector)
            count = locator.count()
            for index in range(min(count, 5)):
                item = locator.nth(index)
                if item.is_visible(timeout=1000):
                    item.click(timeout=5000)
                    return
        except Exception:
            continue
    raise RuntimeError(RegistrationErrorCode.GOOGLE_POPUP_NOT_FOUND.value)


def wait_for_google_popup(page: Any, timeout_ms: int = 15000):
    context = page.context
    before_pages = list(context.pages)
    try:
        with page.expect_popup(timeout=timeout_ms) as popup_info:
            click_continue_with_google(page)
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        return popup
    except Exception as exc:
        if str(exc) == RegistrationErrorCode.GOOGLE_POPUP_NOT_FOUND.value:
            raise

    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        for candidate in context.pages:
            if candidate not in before_pages and is_google_page(candidate):
                candidate.wait_for_load_state("domcontentloaded", timeout=5000)
                return candidate
        if is_google_page(page):
            return page
        time.sleep(0.5)
    raise RuntimeError(RegistrationErrorCode.GOOGLE_POPUP_NOT_FOUND.value)


def run_google_login_from_tiktok_login_page(
    page: Any,
    account: Mapping[str, Any],
    credentials: Any,
    conn: Any,
    platform: str,
) -> tuple[Any, RegistrationResult | None, bool]:
    account_id = str(account.get("id") or "")
    google_page = None
    if not is_tiktok_login_page(page):
        return google_page, None, False

    for google_attempt in range(1, GOOGLE_LOGIN_MAX_ATTEMPTS + 1):
        google_page = wait_for_google_popup(page)
        runtime.log_action(
            conn,
            platform,
            account_id,
            "register_google_start",
            "ok",
            f"attempt={google_attempt}; url={getattr(google_page, 'url', '')}",
        )
        google_result = run_google_login_flow(
            google_page,
            page,
            account,
            credentials,
            conn,
            platform,
        )
        if google_result is not None:
            return google_page, google_result, True
        if wait_for_tiktok_login_prompt_stuck(page, LOGIN_PROMPT_RETRY_SECONDS):
            runtime.log_action(
                conn,
                platform,
                account_id,
                "register_google_retry",
                "retry",
                f"attempt={google_attempt}; reason=tiktok_login_prompt_stuck_{LOGIN_PROMPT_RETRY_SECONDS}s",
            )
            close_page_safely(google_page)
            continue
        return google_page, None, True

    return google_page, RegistrationResult(
        platform=platform,
        account_id=account_id,
        status=RegistrationStatus.ERROR,
        detail=(
            "TikTok stayed on the login page after "
            f"{GOOGLE_LOGIN_MAX_ATTEMPTS} Google login attempts"
        ),
        error_code=RegistrationErrorCode.GOOGLE_FLOW_BLOCKED,
    ), True


def select_existing_google_account(
    google_page: Any,
    tiktok_page: Any,
    account: Mapping[str, Any],
    conn: Any,
    platform: str,
    timeout_ms: int = 60000,
) -> tuple[bool, RegistrationResult | None]:
    account_id = str(account.get("id") or "")
    chooser = wait_for_google_account_chooser(google_page, timeout_ms=timeout_ms)
    if chooser is None:
        return False, None

    try:
        chooser.click(timeout=5000)
        runtime.log_action(
            conn,
            platform,
            account_id,
            "register_google_account_selected",
            "ok",
            "existing Google account selected",
        )
    except Exception as exc:
        return True, RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail=registration_network_error_detail(exc, action="Google account chooser"),
            error_code=RegistrationErrorCode.GOOGLE_FLOW_BLOCKED,
        )

    challenge = wait_for_google_return_or_challenge(google_page, tiktok_page, timeout_ms=60000)
    if challenge:
        return True, google_manual_result(
            account,
            platform,
            google_page,
            challenge,
            "Google challenge detected after choosing existing account",
            conn,
        )
    return True, None


def wait_for_google_account_chooser(page: Any, timeout_ms: int = 60000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if not is_google_account_chooser_page(page):
            if (
                first_visible_locator(page, GOOGLE_EMAIL_SELECTORS, timeout=500) is not None
                or first_visible_locator(page, GOOGLE_PASSWORD_SELECTORS, timeout=500) is not None
                or detect_google_challenge(page)
            ):
                return None
            time.sleep(0.5)
            continue
        chooser = google_account_above_use_another(page)
        if chooser is not None:
            return chooser
        time.sleep(0.5)
    return None


def is_google_account_chooser_page(page: Any) -> bool:
    url = (getattr(page, "url", "") or "").lower()
    if "accountchooser" in url:
        return True
    text = google_page_text(page).lower()
    return "choose an account" in text and "use another account" in text


def google_account_above_use_another(page: Any):
    for selector in GOOGLE_ACCOUNT_CHOOSER_SELECTORS:
        item = first_visible_locator(page, [selector], timeout=500)
        if item is not None:
            return item
    try:
        use_another = page.locator('text=/Use another account/i').first
        if use_another.is_visible(timeout=500):
            candidate = use_another.locator(
                'xpath=ancestor::*[@role="link" or @role="button" or self::li or self::div][1]'
                '/preceding-sibling::*[1]'
            )
            if candidate.is_visible(timeout=500):
                return candidate
    except Exception:
        pass
    return None


def run_google_login_flow(
    google_page: Any,
    tiktok_page: Any,
    account: Mapping[str, Any],
    credentials: Any,
    conn: Any,
    platform: str,
) -> RegistrationResult | None:
    account_id = str(account.get("id") or "")
    chooser_selected, chooser_result = select_existing_google_account(
        google_page,
        tiktok_page,
        account,
        conn,
        platform,
    )
    if chooser_selected:
        return chooser_result

    if not credentials.username:
        return google_manual_result(
            account,
            platform,
            google_page,
            "google_email_missing",
            "Google login email is not configured for this account",
            conn,
        )

    email_input = first_visible_locator(google_page, GOOGLE_EMAIL_SELECTORS, timeout=7000)
    if email_input is None:
        challenge = detect_google_challenge(google_page)
        if challenge:
            return google_manual_result(
                account,
                platform,
                google_page,
                challenge,
                "Google challenge detected before email entry",
                conn,
            )
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail="Google email field was not found",
            error_code=RegistrationErrorCode.GOOGLE_EMAIL_FIELD_NOT_FOUND,
        )

    email_input.fill(credentials.username, timeout=5000)
    runtime.log_action(conn, platform, account_id, "register_google_email", "ok", "email entered")
    try:
        click_google_next(google_page)
    except RuntimeError as exc:
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail=str(exc),
            error_code=RegistrationErrorCode.GOOGLE_FLOW_BLOCKED,
        )

    challenge = wait_for_google_password_or_challenge(google_page)
    if challenge:
        return google_manual_result(
            account,
            platform,
            google_page,
            challenge,
            "Google challenge detected after email entry",
            conn,
        )

    if not credentials.password:
        return google_manual_result(
            account,
            platform,
            google_page,
            "google_password_missing",
            "Google password is not available in local secure storage",
            conn,
        )

    password_input = first_visible_locator(google_page, GOOGLE_PASSWORD_SELECTORS, timeout=7000)
    if password_input is None:
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail="Google password field was not found",
            error_code=RegistrationErrorCode.GOOGLE_PASSWORD_FIELD_NOT_FOUND,
        )

    password_input.fill(credentials.password, timeout=5000)
    runtime.log_action(conn, platform, account_id, "register_google_password", "ok", "password entered")
    try:
        click_google_next(google_page)
    except RuntimeError as exc:
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.ERROR,
            detail=str(exc),
            error_code=RegistrationErrorCode.GOOGLE_FLOW_BLOCKED,
        )

    challenge = wait_for_google_return_or_challenge(google_page, tiktok_page)
    if challenge:
        return google_manual_result(
            account,
            platform,
            google_page,
            challenge,
            "Google challenge detected after password entry",
            conn,
        )
    return None


def run_tiktok_signup_steps(
    page: Any,
    account: Mapping[str, Any],
    conn: Any,
    platform: str,
    birthday: Mapping[str, int],
    planned_username: str,
) -> tuple[str, RegistrationResult | None]:
    account_id = str(account.get("id") or "")
    wait_for_tiktok_signup_state(page)

    if is_tiktok_birthday_page(page):
        try:
            select_tiktok_birthday(page, birthday)
            runtime.log_action(conn, platform, account_id, "register_birthday", "ok", "birthday submitted")
        except Exception as exc:
            detail = registration_network_error_detail(exc, action="birthday form")
            return planned_username, RegistrationResult(
                platform=platform,
                account_id=account_id,
                status=RegistrationStatus.ERROR,
                detail=detail,
                error_code=RegistrationErrorCode.TIKTOK_BIRTHDAY_FORM_NOT_FOUND,
                username=planned_username,
            )
        wait_for_tiktok_signup_state(page)

    if is_tiktok_username_page(page):
        username_result = submit_tiktok_username(
            page,
            account,
            conn,
            platform,
            planned_username,
        )
        if isinstance(username_result, RegistrationResult):
            return planned_username, username_result
        return username_result, None

    return planned_username, None


def wait_for_tiktok_signup_state(page: Any, timeout_ms: int = 60000) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if is_tiktok_birthday_page(page) or is_tiktok_username_page(page):
            return
        if is_tiktok_registration_page(page):
            return
        time.sleep(0.5)


def wait_for_tiktok_login_prompt_stuck(page: Any, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not is_tiktok_login_google_prompt(page):
            return False
        time.sleep(0.5)
    return is_tiktok_login_google_prompt(page)


def is_tiktok_login_page(page: Any) -> bool:
    url = (getattr(page, "url", "") or "").lower()
    if "tiktok.com/login" in url or "/login" in url:
        return True
    text = page_body_text(page).lower()
    return "log in to tiktok" in text


def is_tiktok_login_google_prompt(page: Any) -> bool:
    url = (getattr(page, "url", "") or "").lower()
    if "tiktok.com/login" not in url and "/login" not in url:
        return False
    if first_visible_locator(page, CONTINUE_WITH_GOOGLE_SELECTORS, timeout=500) is not None:
        return True
    text = page_body_text(page).lower()
    return "log in to tiktok" in text and "continue with google" in text


def is_tiktok_birthday_page(page: Any) -> bool:
    if first_visible_locator(page, [BIRTHDAY_SELECTORS["page"]], timeout=500) is not None:
        return True
    text = page_body_text(page).lower()
    return "when's your birthday" in text or (
        "birthday" in text and "month" in text and "year" in text
    )


def select_tiktok_birthday(page: Any, birthday: Mapping[str, int]) -> None:
    year = int(birthday["year"])
    month = int(birthday["month"])
    day = int(birthday["day"])
    if year >= 2006:
        raise RuntimeError(RegistrationErrorCode.TIKTOK_BIRTHDAY_FORM_NOT_FOUND.value)

    select_tiktok_dropdown_option(
        page,
        [BIRTHDAY_SELECTORS["month"], 'select[aria-label*="Month" i]'],
        [MONTH_NAMES[month - 1], str(month)],
    )
    select_tiktok_dropdown_option(
        page,
        [BIRTHDAY_SELECTORS["day"], 'select[aria-label*="Day" i]'],
        [str(day)],
    )
    select_tiktok_dropdown_option(
        page,
        [BIRTHDAY_SELECTORS["year"], 'select[aria-label*="Year" i]'],
        [str(year)],
    )

    next_button = first_visible_locator(page, [BIRTHDAY_SELECTORS["next"]], timeout=3000)
    if next_button is None:
        raise RuntimeError(RegistrationErrorCode.TIKTOK_BIRTHDAY_FORM_NOT_FOUND.value)
    next_button.click(timeout=5000)


def select_tiktok_dropdown_option(page: Any, selectors: list[str], values: list[str]) -> None:
    control = first_visible_locator(page, selectors, timeout=3000)
    if control is None:
        raise RuntimeError(RegistrationErrorCode.TIKTOK_BIRTHDAY_FORM_NOT_FOUND.value)

    for value in values:
        try:
            control.select_option(label=value, timeout=3000)
            return
        except Exception:
            try:
                control.select_option(value=value, timeout=3000)
                return
            except Exception:
                pass

    control.click(timeout=5000)
    for _ in range(12):
        for value in values:
            option = first_visible_locator(
                page,
                [
                    f'[role="option"]:has-text("{value}")',
                    f'li:has-text("{value}")',
                    f'[data-e2e*="option"]:has-text("{value}")',
                    f'[class*="option" i]:has-text("{value}")',
                    f'text="{value}"',
                ],
                timeout=500,
            )
            if option is not None:
                option.click(timeout=5000)
                return
        try:
            page.mouse.wheel(0, 500)
        except Exception:
            break
        time.sleep(0.1)

    for value in values:
        try:
            page.keyboard.type(value)
            page.keyboard.press("Enter")
            return
        except Exception:
            continue
    raise RuntimeError(RegistrationErrorCode.TIKTOK_BIRTHDAY_FORM_NOT_FOUND.value)


def is_tiktok_username_page(page: Any) -> bool:
    if is_tiktok_login_google_prompt(page):
        return False
    if first_visible_locator(page, [USERNAME_SELECTORS["input"]], timeout=500) is not None:
        text = page_body_text(page).lower()
        return "username" in text or "sign up" in text
    text = page_body_text(page).lower()
    return "create username" in text or ("username" in text and "sign up" in text)


def submit_tiktok_username(
    page: Any,
    account: Mapping[str, Any],
    conn: Any,
    platform: str,
    planned_username: str,
    max_retries: int = 5,
) -> str | RegistrationResult:
    account_id = str(account.get("id") or "")
    username = planned_username
    for attempt in range(max_retries):
        if attempt > 0:
            username = generate_unique_username(platform)
        input_locator = first_visible_locator(page, [USERNAME_SELECTORS["input"]], timeout=60000)
        if input_locator is None:
            return RegistrationResult(
                platform=platform,
                account_id=account_id,
                status=RegistrationStatus.ERROR,
                detail="TikTok username input was not found",
                error_code=RegistrationErrorCode.USERNAME_FORM_NOT_FOUND,
                username=username,
            )
        input_locator.fill(username, timeout=5000)

        submit_button = first_visible_locator(page, [USERNAME_SELECTORS["submit"]], timeout=60000)
        if submit_button is None:
            return RegistrationResult(
                platform=platform,
                account_id=account_id,
                status=RegistrationStatus.ERROR,
                detail="TikTok username submit button was not found",
                error_code=RegistrationErrorCode.USERNAME_FORM_NOT_FOUND,
                username=username,
            )
        submit_button.click(timeout=5000)

        if wait_for_username_unavailable(page):
            runtime.log_action(
                conn,
                platform,
                account_id,
                "register_username",
                "retry",
                f"attempt={attempt + 1}; reason=username_unavailable",
            )
            continue

        record_username(username, account, platform)
        runtime.log_action(
            conn,
            platform,
            account_id,
            "register_username",
            "ok",
            f"username={username}",
        )
        return username

    detail = f"TikTok username was unavailable after {max_retries} attempts"
    return RegistrationResult(
        platform=platform,
        account_id=account_id,
        status=RegistrationStatus.ERROR,
        detail=detail,
        error_code=RegistrationErrorCode.USERNAME_UNAVAILABLE,
        username=username,
    )


def wait_for_username_unavailable(page: Any, timeout_ms: int = 4000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        text = page_body_text(page).lower()
        if any(pattern in text for pattern in USERNAME_UNAVAILABLE_PATTERNS):
            return True
        time.sleep(0.5)
    return False


def first_visible_locator(page: Any, selectors: list[str], timeout: int = 1000):
    deadline = time.time() + (timeout / 1000)
    while True:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = locator.count()
                for index in range(min(count, 5)):
                    item = locator.nth(index)
                    remaining_ms = max(100, int((deadline - time.time()) * 1000))
                    if item.is_visible(timeout=min(remaining_ms, 500)):
                        return item
            except Exception:
                continue
        if time.time() >= deadline:
            return None
        time.sleep(0.5)
    return None


def click_google_next(page: Any) -> None:
    button = first_visible_locator(page, GOOGLE_NEXT_SELECTORS, timeout=3000)
    if button is None:
        try:
            page.mouse.wheel(0, 600)
            time.sleep(0.5)
        except Exception:
            pass
        button = first_visible_locator(page, GOOGLE_NEXT_SELECTORS, timeout=3000)
    if button is None:
        raise RuntimeError(RegistrationErrorCode.GOOGLE_FLOW_BLOCKED.value)
    button.click(timeout=5000)


def wait_for_google_password_or_challenge(page: Any, timeout_ms: int = 20000) -> str | None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        challenge = detect_google_challenge(page)
        if challenge:
            return challenge
        if first_visible_locator(page, GOOGLE_PASSWORD_SELECTORS, timeout=500) is not None:
            return None
        time.sleep(0.5)
    return detect_google_challenge(page)


def wait_for_google_return_or_challenge(
    google_page: Any,
    tiktok_page: Any,
    timeout_ms: int = 45000,
) -> str | None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            if google_page.is_closed():
                return None
        except Exception:
            return None
        challenge = detect_google_challenge(google_page)
        if challenge:
            return challenge
        if not is_google_page(google_page) or is_tiktok_registration_page(tiktok_page):
            return None
        time.sleep(0.75)
    return detect_google_challenge(google_page) or "google_security_check"


def detect_google_challenge(page: Any) -> str | None:
    text = google_page_text(page).lower()
    for reason, patterns in GOOGLE_CHALLENGE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return reason
    return None


def google_page_text(page: Any) -> str:
    return page_body_text(page)


def page_body_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=1000)
    except Exception:
        try:
            return str(page.evaluate("() => document.body ? document.body.innerText : ''") or "")
        except Exception:
            return ""


def close_page_safely(page: Any) -> None:
    try:
        if page is not None and not page.is_closed():
            page.close()
    except Exception:
        pass


def google_manual_result(
    account: Mapping[str, Any],
    platform: str,
    page: Any,
    reason: str,
    detail: str,
    conn: Any,
) -> RegistrationResult | None:
    account_id = str(account.get("id") or "")
    state = "captcha" if "captcha" in reason else "mfa" if "mfa" in reason else "security_check"
    require_manual_intervention(account, platform, state, reason, detail, page)
    runtime.log_action(conn, platform, account_id, "register_manual_required", "pending", reason)
    action = wait_for_manual_intervention(account)
    if action == "continue":
        runtime.session_log(f"{account_id} | REGISTER MANUAL CONTINUE | reason={reason}", platform)
        return None
    if action == "skip":
        return RegistrationResult(
            platform=platform,
            account_id=account_id,
            status=RegistrationStatus.MANUAL_REQUIRED,
            detail=f"user skipped registration after {reason}",
            error_code=RegistrationErrorCode.MANUAL_INTERVENTION_REQUIRED,
            manual_reason=reason,
        )
    raise RuntimeError("stopped by user during Google registration intervention")


def is_google_page(page: Any) -> bool:
    url = (getattr(page, "url", "") or "").lower()
    return "accounts.google." in url or "google.com" in url and "/signin" in url


def is_tiktok_registration_page(page: Any) -> bool:
    url = (getattr(page, "url", "") or "").lower()
    if "tiktok.com" not in url:
        return False
    if "/login" in url or "login?" in url:
        return False
    return not any(marker in url for marker in ("accounts.google.", "google.com/signin"))


def finalize_tiktok_registration_session(
    page: Any,
    account: Mapping[str, Any],
    conn: Any,
    platform: str,
) -> None:
    account_id = str(account.get("id") or "")
    if click_tiktok_google_one_tap(page, timeout=1500):
        runtime.log_action(
            conn,
            platform,
            account_id,
            "register_tiktok_google_continue",
            "ok",
            "TikTok Google one-tap confirmation clicked",
        )
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        time.sleep(15)

    if complete_tiktok_interest_onboarding(page, account, conn, platform):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        time.sleep(5)


def complete_tiktok_interest_onboarding(
    page: Any,
    account: Mapping[str, Any],
    conn: Any,
    platform: str,
) -> bool:
    if not is_tiktok_interest_onboarding_page(page):
        return False

    account_id = str(account.get("id") or "")
    selected = 0
    for selector in TIKTOK_INTEREST_SELECTORS:
        if selected >= 3:
            break
        option = first_visible_locator(page, [selector], timeout=800)
        if option is None:
            continue
        try:
            option.click(timeout=3000)
            selected += 1
            time.sleep(0.3)
        except Exception:
            continue

    continue_button = first_visible_locator(page, TIKTOK_INTEREST_CONTINUE_SELECTORS, timeout=3000)
    if selected >= 3 and continue_button is not None:
        try:
            continue_button.click(timeout=5000)
            runtime.log_action(
                conn,
                platform,
                account_id,
                "register_onboarding_interests",
                "ok",
                f"selected={selected}",
            )
            return True
        except Exception as exc:
            runtime.log_action(
                conn,
                platform,
                account_id,
                "register_onboarding_interests",
                "error",
                registration_network_error_detail(exc, action="TikTok onboarding"),
            )
            return False

    runtime.log_action(
        conn,
        platform,
        account_id,
        "register_onboarding_interests",
        "error",
        f"selected={selected}; continue_button_found={continue_button is not None}",
    )
    return False


def is_tiktok_interest_onboarding_page(page: Any) -> bool:
    text = page_body_text(page).lower()
    return (
        "what would you like to watch on tiktok" in text
        or "continue (0/3)" in text
    )


def detect_registration_complete(page: Any, account_id: str) -> bool:
    try:
        result = classify_tiktok_page(page, account_id=account_id)
        return result.logged_in
    except Exception:
        return False


def registration_network_error_detail(exc: Exception, action: str = "registration") -> str:
    detail = runtime.redact_runtime_text(f"{type(exc).__name__}: {exc}")
    return f"TikTok registration {action} failed: detail={detail}"


def registration_error_code_for_exception(
    exc: Exception,
    default: RegistrationErrorCode,
) -> RegistrationErrorCode:
    text = str(exc)
    for code in RegistrationErrorCode:
        if text == code.value or code.value in text:
            return code
    return default


def adapter() -> RegistrationAdapter:
    return TikTokGoogleRegistrationAdapter()
