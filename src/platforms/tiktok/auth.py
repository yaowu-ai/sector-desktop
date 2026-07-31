"""TikTok authentication state detection."""
from __future__ import annotations

import re
import os
import time
from typing import Any, Mapping

from auth_adapters import AuthResult, InterventionState, LoginState


TIKTOK_FORYOU_URL = "https://www.tiktok.com/foryou"
TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"
LOCAL_CREDENTIAL_SOURCES = {"local_secure_store", "dpapi"}


LOGGED_IN_SELECTORS = [
    '[data-e2e="profile-icon"]',
    '[data-e2e="nav-profile"]',
    'a[href*="/upload"]',
    'button[aria-label*="Like" i]',
    '[data-e2e="feed-follow"]',
    '[data-e2e="comment-icon"]',
]

LOGIN_PAGE_SELECTORS = [
    'input[name="username"]',
    'input[name="email"]',
    'input[type="password"]',
    '[data-e2e="login-password"]',
    '[data-e2e="login-phone"]',
    '[data-e2e="login-button"]',
]

LOGGED_OUT_SELECTORS = [
    '[data-e2e="top-login-button"]',
    'button:has-text("Log in")',
    '[role="button"]:has-text("Log in")',
    'button:has-text("登录")',
    'text=/Log in to TikTok/i',
    'text=/Sign up for TikTok/i',
    'text=/登录 TikTok/i',
]

GOOGLE_ONE_TAP_SELECTORS = [
    'button:has-text("Continue as")',
    '[role="button"]:has-text("Continue as")',
    'text=/Continue as .+/i',
]

SESSION_BLOCKING_SELECTORS = [
    *LOGGED_OUT_SELECTORS,
    *GOOGLE_ONE_TAP_SELECTORS,
    'text=/Sign in to tiktok\\.com with google\\.com/i',
    'text=/What would you like to watch on TikTok/i',
    'button:has-text("Continue (0/3)")',
]

CAPTCHA_PATTERNS = [
    r"\bcaptcha\b",
    r"security verification",
    r"verification puzzle",
    r"drag (the )?slider",
    r"slide to verify",
    r"verify you are human",
    r"请完成验证",
    r"拖动滑块",
    r"验证码",
]

MFA_PATTERNS = [
    r"two[- ]step verification",
    r"2[- ]step verification",
    r"two[- ]factor",
    r"verification code",
    r"enter (the )?code",
    r"authenticator",
    r"短信验证码",
    r"二次验证",
    r"两步验证",
]

SECURITY_CHECK_PATTERNS = [
    r"security check",
    r"secure your account",
    r"confirm your identity",
    r"verify it'?s you",
    r"suspicious activity",
    r"unusual activity",
    r"账号安全",
    r"安全确认",
    r"身份验证",
]


class TikTokAuthAdapter:
    platform = "tiktok"

    def ensure_logged_in(
        self,
        page: Any,
        account: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> AuthResult:
        account_id = str(account.get("id") or "") or None
        try:
            page.goto(TIKTOK_FORYOU_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            time.sleep(3)
        except Exception as exc:
            return AuthResult(
                platform=self.platform,
                account_id=account_id,
                state=LoginState.UNKNOWN,
                detail=f"failed to load TikTok page: {type(exc).__name__}: {exc}",
                url=getattr(page, "url", None),
                error_code="AUTH_TIKTOK_LOAD_FAILED",
                intervention=_intervention(LoginState.UNKNOWN, "load_failed"),
            )
        result = classify_tiktok_page(page, account_id=account_id)
        if result.state == LoginState.LOGGED_IN:
            return result
        if result.state in {LoginState.MFA, LoginState.CAPTCHA, LoginState.SECURITY_CHECK}:
            return result
        if click_tiktok_google_one_tap(page):
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(15)
            result = classify_tiktok_page(page, account_id=account_id)
            if result.state == LoginState.LOGGED_IN:
                return result
            if result.state in {LoginState.MFA, LoginState.CAPTCHA, LoginState.SECURITY_CHECK}:
                return result
        if not auto_login_enabled(account):
            return result
        username = login_username(account)
        password = login_password(account)
        if not username or not password:
            return AuthResult(
                platform=self.platform,
                account_id=account_id,
                state=result.state,
                detail="auto login is enabled but username or password env is missing",
                url=result.url,
                error_code="AUTH_TIKTOK_CREDENTIAL_MISSING",
                intervention=_intervention(result.state, "credential_missing"),
            )
        return submit_password_login(page, account_id, username, password)

    def open_login_page(self, page: Any) -> AuthResult:
        try:
            page.goto(TIKTOK_LOGIN_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception as exc:
            return AuthResult(
                platform=self.platform,
                state=LoginState.UNKNOWN,
                detail=f"failed to open TikTok login page: {type(exc).__name__}: {exc}",
                url=getattr(page, "url", None),
                error_code="AUTH_TIKTOK_LOGIN_PAGE_FAILED",
                intervention=_intervention(LoginState.UNKNOWN, "load_failed"),
            )
        return classify_tiktok_page(page)


def auto_login_enabled(account: Mapping[str, Any]) -> bool:
    login = account.get("login") if isinstance(account, Mapping) else None
    return isinstance(login, Mapping) and bool(login.get("enabled"))


def login_username(account: Mapping[str, Any]) -> str:
    env_account = os.environ.get("AM_LOGIN_ACCOUNT_ID", "").strip()
    account_id = str(account.get("id") or "").strip()
    if env_account and account_id and env_account != account_id:
        return ""
    value = os.environ.get("AM_LOGIN_USERNAME", "").strip()
    if value:
        return value
    login = account.get("login") if isinstance(account, Mapping) else None
    if isinstance(login, Mapping):
        return str(login.get("username") or "").strip()
    return ""


def login_password(account: Mapping[str, Any]) -> str:
    env_account = os.environ.get("AM_LOGIN_ACCOUNT_ID", "").strip()
    account_id = str(account.get("id") or "").strip()
    if env_account and account_id and env_account != account_id:
        return ""
    source = os.environ.get("AM_LOGIN_CREDENTIAL_SOURCE", "").strip().lower()
    if source not in LOCAL_CREDENTIAL_SOURCES:
        return ""
    return os.environ.get("AM_LOGIN_PASSWORD", "")


def submit_password_login(page: Any, account_id: str | None, username: str, password: str) -> AuthResult:
    try:
        if not _is_login_url(getattr(page, "url", "") or ""):
            page.goto(TIKTOK_LOGIN_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        open_password_login_mode(page)
        username_locator = first_visible_locator(page, USERNAME_SELECTORS)
        password_locator = first_visible_locator(page, PASSWORD_SELECTORS)
        if username_locator is None or password_locator is None:
            return _result(
                state=LoginState.LOGIN_PAGE,
                detail="TikTok login form detected but username/password fields were not found",
                account_id=account_id,
                url=getattr(page, "url", "") or "",
                intervention_reason="login_form_not_found",
            )
        username_locator.fill(username, timeout=5000)
        password_locator.fill(password, timeout=5000)
        submit = first_visible_locator(page, SUBMIT_SELECTORS)
        if submit is None:
            password_locator.press("Enter")
        else:
            submit.click(timeout=5000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        time.sleep(5)
    except Exception as exc:
        return AuthResult(
            platform="tiktok",
            account_id=account_id,
            state=LoginState.UNKNOWN,
            detail=f"TikTok password login submit failed: {type(exc).__name__}: {exc}",
            url=getattr(page, "url", None),
            error_code="AUTH_TIKTOK_SUBMIT_FAILED",
            intervention=_intervention(LoginState.UNKNOWN, "submit_failed"),
        )
    return classify_tiktok_page(page, account_id=account_id)


USERNAME_SELECTORS = [
    'input[name="username"]',
    'input[name="email"]',
    'input[autocomplete="username"]',
    'input[type="email"]',
    'input[placeholder*="Email" i]',
    'input[placeholder*="username" i]',
    'input[placeholder*="phone" i]',
    'input[type="text"]',
]

PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    '[data-e2e="login-password"] input',
]

SUBMIT_SELECTORS = [
    '[data-e2e="login-button"]',
    'button[type="submit"]',
    'button:has-text("Log in")',
    'button:has-text("登录")',
]

PASSWORD_MODE_SELECTORS = [
    'text=/Use phone \\/ email \\/ username/i',
    'text=/Log in with phone or email/i',
    'text=/Email \\/ Username/i',
    'text=/Phone \\/ email \\/ username/i',
    'text=/使用手机号|邮箱|用户名/',
]


def open_password_login_mode(page: Any) -> None:
    for selector in PASSWORD_MODE_SELECTORS:
        locator = first_visible_locator(page, [selector], timeout=700)
        if locator is None:
            continue
        try:
            locator.click(timeout=1000)
            time.sleep(1)
        except Exception:
            pass


def first_visible_locator(page: Any, selectors: list[str], timeout: int = 1000):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()
            for index in range(min(count, 5)):
                item = locator.nth(index)
                if item.is_visible(timeout=timeout):
                    return item
        except Exception:
            continue
    return None


def classify_tiktok_page(page: Any, account_id: str | None = None) -> AuthResult:
    url = getattr(page, "url", "") or ""
    text = _page_text(page)
    lowered = text.lower()

    state = _classify_challenge(lowered)
    if state:
        return _result(
            state=state,
            detail=f"TikTok {state.value} detected",
            account_id=account_id,
            url=url,
            intervention_reason=state.value,
        )

    if _is_login_url(url) or _visible_total(page, LOGIN_PAGE_SELECTORS) > 0:
        return _result(
            state=LoginState.LOGIN_PAGE,
            detail="TikTok login page or login form detected",
            account_id=account_id,
            url=url,
            intervention_reason="login_required",
        )

    blocking_details = _session_blocking_details(page, lowered)
    if blocking_details:
        return _result(
            state=LoginState.LOGGED_OUT,
            detail=f"TikTok session is not complete: {', '.join(blocking_details)}",
            account_id=account_id,
            url=url,
            intervention_reason="login_required",
        )

    logged_in_hits = _visible_total(page, LOGGED_IN_SELECTORS)
    if logged_in_hits:
        return _result(
            state=LoginState.LOGGED_IN,
            detail=f"interactive TikTok controls detected ({logged_in_hits})",
            account_id=account_id,
            url=url,
        )

    logged_out_hits = _visible_total(page, LOGGED_OUT_SELECTORS)
    if logged_out_hits or _looks_logged_out(lowered):
        return _result(
            state=LoginState.LOGGED_OUT,
            detail="TikTok logged-out prompt detected",
            account_id=account_id,
            url=url,
            intervention_reason="login_required",
        )

    title = _page_title(page)
    return _result(
        state=LoginState.UNKNOWN,
        detail=f"unable to classify TikTok login state; title={title}",
        account_id=account_id,
        url=url,
        intervention_reason="unknown",
    )


def _classify_challenge(lowered_text: str) -> LoginState | None:
    for state, patterns in (
        (LoginState.CAPTCHA, CAPTCHA_PATTERNS),
        (LoginState.MFA, MFA_PATTERNS),
        (LoginState.SECURITY_CHECK, SECURITY_CHECK_PATTERNS),
    ):
        if any(re.search(pattern, lowered_text, flags=re.I) for pattern in patterns):
            return state
    return None


def click_tiktok_google_one_tap(page: Any, timeout: int = 1000) -> bool:
    button = first_visible_locator(page, GOOGLE_ONE_TAP_SELECTORS, timeout=timeout)
    if button is None:
        return False
    try:
        button.click(timeout=5000)
        return True
    except Exception:
        return False


def _session_blocking_details(page: Any, lowered_text: str) -> list[str]:
    details: list[str] = []
    if _visible_total(page, LOGGED_OUT_SELECTORS) > 0 or _looks_logged_out(lowered_text):
        details.append("login prompt visible")
    if _visible_total(page, GOOGLE_ONE_TAP_SELECTORS) > 0 or (
        "sign in to tiktok.com with google.com" in lowered_text
        and "continue as" in lowered_text
    ):
        details.append("Google one-tap confirmation visible")
    if _looks_interest_onboarding(lowered_text):
        details.append("TikTok onboarding prompt visible")
    return details


def _looks_logged_out(lowered_text: str) -> bool:
    return (
        "log in to tiktok" in lowered_text
        or "sign up for tiktok" in lowered_text
        or "continue with google" in lowered_text
    )


def _looks_interest_onboarding(lowered_text: str) -> bool:
    return (
        "what would you like to watch on tiktok" in lowered_text
        or "continue (0/3)" in lowered_text
    )


def _is_login_url(url: str) -> bool:
    lowered = url.lower()
    return "/login" in lowered or "login?" in lowered


def _visible_total(page: Any, selectors: list[str]) -> int:
    return sum(_visible_count(page, selector) for selector in selectors)


def _visible_count(page: Any, selector: str, timeout: int = 800) -> int:
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


def _page_text(page: Any) -> str:
    try:
        return page.locator("body").inner_text(timeout=1000)
    except Exception:
        try:
            return str(page.evaluate("() => document.body ? document.body.innerText : ''") or "")
        except Exception:
            return ""


def _page_title(page: Any) -> str:
    try:
        return page.title(timeout=1000)
    except Exception:
        return ""


def _result(
    state: LoginState,
    detail: str,
    account_id: str | None,
    url: str,
    intervention_reason: str | None = None,
) -> AuthResult:
    intervention = None
    if state != LoginState.LOGGED_IN:
        intervention = _intervention(state, intervention_reason or state.value, detail)
    return AuthResult(
        platform="tiktok",
        account_id=account_id,
        state=state,
        detail=detail,
        url=url,
        error_code=None if state == LoginState.LOGGED_IN else f"AUTH_TIKTOK_{state.value.upper()}",
        intervention=intervention,
    )


def _intervention(
    state: LoginState,
    reason: str,
    detail: str = "",
) -> InterventionState:
    return InterventionState(
        required=True,
        state=state,
        reason=reason,
        detail=detail,
    )
