"""Prepare a BitBrowser profile for Google account setup.

Phase 1 implemented here:
  1. Find a BitBrowser profile by its exact window name.
  2. Open or attach to that profile.
  3. Open Google, type a search query, and submit it.
  4. Click Google's visible Sign in link.
  5. Optionally enter the Google account email address.
  6. Click Next and verify Google's password page appears.
  7. Optionally enter the Google account password.
  8. Click Next and report signed-in, challenge, or rejected state.
  9. Accept the Workspace first-login notice when it appears.
  10. Open Google Account and click Google password.
  11. Optionally fill and confirm a new password.
  12. Submit the password change and verify the result.
  13. Leave the BitBrowser window open for inspection.

Security challenges are left open for manual handling.
"""
import argparse
import getpass
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from patchright.sync_api import TimeoutError as PlaywrightTimeoutError

from bitbrowser import BitBrowserClient
from patchright_runtime import start_sync_playwright


GOOGLE_HOME = "https://www.google.com/"
SEARCH_BOX_SELECTORS = (
    'textarea[name="q"]',
    'input[name="q"]',
)
SIGN_IN_SELECTORS = (
    'a[href*="accounts.google.com/ServiceLogin"]',
    'a[href*="accounts.google.com"][aria-label*="Sign in" i]',
    'a[href*="accounts.google.com"][aria-label*="Iniciar sesión" i]',
)
EMAIL_INPUT_SELECTORS = (
    'input#identifierId',
    'input[name="identifier"]',
    'input[type="email"]',
)
IDENTIFIER_NEXT_SELECTORS = (
    '#identifierNext button',
    'button[type="button"]:has-text("Next")',
    'button[type="button"]:has-text("Siguiente")',
    '#identifierNext',
)
PASSWORD_INPUT_SELECTORS = (
    'input[name="Passwd"]',
    'input[type="password"]',
)
PASSWORD_NEXT_SELECTORS = (
    '#passwordNext button',
    '#passwordNext',
    'button[type="button"]:has-text("Next")',
    'button[type="button"]:has-text("Siguiente")',
)
PASSWORD_ERROR_SELECTORS = (
    'div[jsname="B34EJ"]',
)
I_UNDERSTAND_SELECTORS = (
    'button:has-text("I understand")',
    '[role="button"]:has-text("I understand")',
    'button:has-text("Entiendo")',
    '[role="button"]:has-text("Entiendo")',
)
GOOGLE_PASSWORD_LINK_SELECTORS = (
    'a[href*="/signinoptions/password"]',
    '[role="link"][href*="/signinoptions/password"]',
    'a:has-text("Google password")',
    '[role="link"]:has-text("Google password")',
    'a:has-text("Contraseña de Google")',
    '[role="link"]:has-text("Contraseña de Google")',
)
NEW_PASSWORD_INPUT_SELECTORS = (
    'input[name="password"]',
    'input[aria-label="New password"]',
    'input[aria-label="Nueva contraseña"]',
)
CONFIRM_PASSWORD_INPUT_SELECTORS = (
    'input[name="confirmation_password"]',
    'input[aria-label="Confirm new password"]',
    'input[aria-label="Confirmar nueva contraseña"]',
)
CHANGE_PASSWORD_BUTTON_SELECTORS = (
    'button:has-text("Change password")',
    '[role="button"]:has-text("Change password")',
    'button:has-text("Cambiar contraseña")',
    '[role="button"]:has-text("Cambiar contraseña")',
)
PASSWORD_CHANGE_SUCCESS_SELECTORS = (
    '[role="alert"]:has-text("Password changed")',
    '[role="status"]:has-text("Password changed")',
    '[role="alert"]:has-text("Contraseña cambiada")',
    '[role="status"]:has-text("Contraseña cambiada")',
)
PASSWORD_CHANGE_ERROR_SELECTORS = (
    '[role="alert"]',
)
GOOGLE_RESULTS_URL = re.compile(
    r"^https://(?:www\.)?google\.[^/]+/search(?:\?|$)", re.IGNORECASE
)
GOOGLE_ACCOUNTS_URL = re.compile(
    r"^https://accounts\.google\.com/", re.IGNORECASE
)
MY_ACCOUNT_HOME = "https://myaccount.google.com/"
MY_ACCOUNT_PASSWORD_URL = "https://myaccount.google.com/signinoptions/password"
DEFAULT_NEW_PASSWORD = "9p$Fj2*Kb"


def parse_mail_line(value):
    """Parse email----password----ignored-extra-fields."""
    parts = [part.strip() for part in value.strip().split("----")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("邮箱文件格式必须是 账号----密码，可带第三段备注")
    return parts[0], parts[1]


def load_mail_file(path):
    """Load Gmail accounts from a private mail file."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"邮箱文件不存在: {path}")

    accounts = []
    errors = []
    for line_number, raw in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        try:
            email, password = parse_mail_line(value)
        except ValueError as exc:
            errors.append(f"第 {line_number} 行: {exc}")
            continue
        accounts.append({"line": line_number, "email": email, "password": password})

    if errors:
        raise ValueError("邮箱文件格式错误:\n" + "\n".join(errors))
    if not accounts:
        raise ValueError(f"邮箱文件没有有效记录: {path}")
    return accounts


def browser_name_sequence(start_name, count):
    """Generate tiktok_25, tiktok_26... from an exact starting window name."""
    match = re.fullmatch(r"(.+_)(\d+)", start_name.strip())
    if not match:
        raise ValueError("批量模式的 --browser-name 必须以 _数字 结尾，例如 tiktok_25")

    prefix, number_text = match.groups()
    width = len(number_text) if number_text.startswith("0") else 0
    start_number = int(number_text)
    names = []
    for offset in range(count):
        number = start_number + offset
        if width:
            names.append(f"{prefix}{number:0{width}d}")
        else:
            names.append(f"{prefix}{number}")
    return names


def find_profile_by_name(profiles, browser_name):
    """Return one exact profile match; reject missing or duplicate names."""
    matches = [
        profile for profile in profiles
        if isinstance(profile, dict)
        and str(profile.get("name") or "").strip() == browser_name
    ]
    if not matches:
        raise RuntimeError(f"未找到名称为 {browser_name!r} 的比特浏览器窗口")
    if len(matches) > 1:
        raise RuntimeError(
            f"存在 {len(matches)} 个同名窗口 {browser_name!r}，请先保证窗口名称唯一"
        )
    profile_id = matches[0].get("id")
    if not profile_id:
        raise RuntimeError(f"窗口 {browser_name!r} 没有返回 profile id")
    return matches[0]


def choose_page(context):
    """Prefer an existing Google tab; otherwise reuse the first tab."""
    for page in context.pages:
        hostname = urlparse(page.url or "").hostname or ""
        if "google." in hostname:
            return page
    return context.pages[0] if context.pages else context.new_page()


def visible_search_box(page, timeout_ms):
    """Find Google's visible desktop search box across common layouts."""
    return visible_locator(page, SEARCH_BOX_SELECTORS, timeout_ms)


def visible_locator(page, selectors, timeout_ms):
    """Return the first visible locator matching one of `selectors`."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                continue
        time.sleep(0.2)
    return None


def human_type(locator, text):
    """Type into the focused locator with small non-uniform delays."""
    locator.fill("")
    locator.click()
    for character in text:
        locator.press_sequentially(character, delay=random.randint(70, 170))


def search_google(page, query="gmail", timeout_ms=60_000):
    """Open Google, type `query`, submit, and verify a results page loaded."""
    page.goto(GOOGLE_HOME, wait_until="domcontentloaded", timeout=timeout_ms)
    page.bring_to_front()

    search_box = visible_search_box(page, timeout_ms)
    if search_box is None:
        raise RuntimeError(
            "未找到 Google 搜索框；请检查窗口中是否出现同意页、验证码或网络错误"
        )

    human_type(search_box, query)
    search_box.press("Enter")
    try:
        page.wait_for_url(GOOGLE_RESULTS_URL, timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"已提交搜索，但未进入结果页，当前地址: {page.url}"
        ) from exc
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    return page.url


def click_google_sign_in(page, timeout_ms=60_000):
    """Click Google's visible Sign in link and verify the account page loaded."""
    sign_in = visible_locator(page, SIGN_IN_SELECTORS, timeout_ms)
    if sign_in is None:
        raise RuntimeError(
            "未找到 Google 的 Sign in 链接；账号可能已登录，或页面布局发生变化"
        )

    sign_in.click(timeout=timeout_ms)
    try:
        page.wait_for_url(GOOGLE_ACCOUNTS_URL, timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"已点击 Sign in，但未进入 Google 登录页，当前地址: {page.url}"
        ) from exc
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    return page.url


def enter_google_email(page, email, timeout_ms=60_000):
    """Enter an email address on Google's identifier page without submitting."""
    email_input = visible_locator(page, EMAIL_INPUT_SELECTORS, timeout_ms)
    if email_input is None:
        raise RuntimeError(
            "未找到 Google 邮箱输入框；页面可能已登录，或出现了其他验证页面"
        )

    human_type(email_input, email)
    try:
        actual = email_input.input_value(timeout=2_000).strip()
    except Exception as exc:
        raise RuntimeError("无法校验 Google 邮箱输入框内容") from exc
    if actual != email:
        raise RuntimeError(
            f"Google 邮箱输入不完整：期望 {email!r}，实际 {actual!r}"
        )
    return actual


def click_identifier_next(page, timeout_ms=60_000):
    """Submit the identifier form and verify the password input appears."""
    next_button = visible_locator(page, IDENTIFIER_NEXT_SELECTORS, timeout_ms)
    if next_button is None:
        raise RuntimeError("未找到 Google 邮箱页面的 Next 按钮")

    next_button.click(timeout=timeout_ms)
    password_input = visible_locator(page, PASSWORD_INPUT_SELECTORS, timeout_ms)
    if password_input is None:
        raise RuntimeError(
            "已点击 Next，但未进入密码页；可能出现验证码、账号错误或其他验证，"
            f"当前地址: {page.url}"
        )
    return page.url


def enter_google_password(page, password, timeout_ms=60_000):
    """Enter the password without submitting the password form."""
    password_input = visible_locator(page, PASSWORD_INPUT_SELECTORS, timeout_ms)
    if password_input is None:
        raise RuntimeError("未找到 Google 密码输入框")

    human_type(password_input, password)
    try:
        actual = password_input.input_value(timeout=2_000)
    except Exception as exc:
        raise RuntimeError("无法校验 Google 密码输入框内容") from exc
    if actual != password:
        raise RuntimeError("Google 密码输入不完整")
    return len(actual)


def visible_text(page, selectors):
    """Return non-empty text from the first currently-visible locator."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible():
                text = (locator.inner_text(timeout=500) or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None


def click_password_next(page, timeout_ms=60_000):
    """Submit the password form and classify the resulting Google page."""
    next_button = visible_locator(page, PASSWORD_NEXT_SELECTORS, timeout_ms)
    if next_button is None:
        raise RuntimeError("未找到 Google 密码页面的 Next 按钮")

    start_url = page.url
    next_button.click(timeout=timeout_ms)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        error = visible_text(page, PASSWORD_ERROR_SELECTORS)
        if error:
            raise RuntimeError(f"Google 拒绝登录: {error}")

        current_url = page.url
        if current_url != start_url:
            parsed = urlparse(current_url)
            if parsed.hostname != "accounts.google.com":
                return {"status": "signed_in", "url": current_url}
            if "/speedbump/workspacetermsofservice" in parsed.path:
                return {"status": "workspace_terms", "url": current_url}
            if "/challenge/" in parsed.path and "/challenge/pwd" not in parsed.path:
                return {"status": "challenge", "url": current_url}
        time.sleep(0.25)

    raise RuntimeError(
        f"已点击密码页 Next，但页面未在限定时间内变化，当前地址: {page.url}"
    )


def click_i_understand(page, timeout_ms=60_000):
    """Accept Google's Workspace first-login notice and classify the result."""
    button = visible_locator(page, I_UNDERSTAND_SELECTORS, timeout_ms)
    if button is None:
        raise RuntimeError("未找到 Workspace 条款页的 I understand 按钮")

    start_url = page.url
    button.click(timeout=timeout_ms)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        current_url = page.url
        if current_url != start_url:
            parsed = urlparse(current_url)
            if parsed.hostname != "accounts.google.com":
                return {"status": "signed_in", "url": current_url}
            if "/challenge/" in parsed.path:
                return {"status": "challenge", "url": current_url}
        time.sleep(0.25)

    return {"status": "terms_timeout", "url": page.url}


def classify_password_settings_url(current_url):
    """Classify Google password-settings, reauth, and challenge URLs."""
    parsed = urlparse(current_url or "")
    if (parsed.hostname == "myaccount.google.com"
            and "/signinoptions/password" in parsed.path):
        return {"status": "password_settings", "url": current_url}
    if parsed.hostname == "accounts.google.com":
        if "/challenge/pwd" in parsed.path:
            return {"status": "reauth", "url": current_url}
        if "/challenge/" in parsed.path:
            return {"status": "challenge", "url": current_url}
    return None


def wait_for_password_settings_destination(page, timeout_ms=60_000):
    """Wait until Google reaches password settings or a verification page."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        result = classify_password_settings_url(page.url)
        if result is not None:
            return result
        time.sleep(0.25)
    return None


def is_recoverable_navigation_error(exc):
    """Return True for Google redirects that can interrupt page.goto."""
    message = str(exc)
    return (
        isinstance(exc, PlaywrightTimeoutError)
        or "net::ERR_ABORTED" in message
        or "Navigation interrupted" in message
        or "navigating frame was detached" in message
    )


def short_error(exc):
    """Return the first line of a browser exception for compact logs."""
    return str(exc).splitlines()[0]


def goto_google_page(page, url, timeout_ms=60_000):
    """Navigate to a Google page, tolerating redirect-driven aborts."""
    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
        return None
    except Exception as exc:
        if is_recoverable_navigation_error(exc):
            return exc
        raise


def open_google_password_settings(page, timeout_ms=60_000):
    """Open Google Account password settings without depending on UI language."""
    direct_error = goto_google_page(page, MY_ACCOUNT_PASSWORD_URL, timeout_ms)
    if direct_error is not None:
        print(f"      Google 密码页跳转被打断，继续等待: {short_error(direct_error)}")

    direct_result = wait_for_password_settings_destination(
        page, min(timeout_ms, 15_000)
    )
    if direct_result is not None:
        return direct_result

    # Fallback for layouts that do not accept direct navigation: go home and
    # click the localized password navigation item.
    home_error = goto_google_page(page, MY_ACCOUNT_HOME, timeout_ms)
    if home_error is not None:
        print(
            "      Google Account 首页跳转被打断，继续尝试查找入口: "
            f"{short_error(home_error)}"
        )

    home_result = wait_for_password_settings_destination(
        page, min(timeout_ms, 5_000)
    )
    if home_result is not None:
        return home_result

    password_link = visible_locator(
        page, GOOGLE_PASSWORD_LINK_SELECTORS, timeout_ms
    )
    if password_link is None:
        raise RuntimeError(
            "未找到 Google Account 密码入口；页面可能是非预期语言或布局"
        )

    password_link.click(timeout=timeout_ms)
    click_result = wait_for_password_settings_destination(page, timeout_ms)
    if click_result is not None:
        return click_result

    raise RuntimeError(
        "已尝试进入 Google 密码设置，但未进入密码设置或重新验证页面，"
        f"当前地址: {page.url}"
    )


def complete_google_password_reauth(page, password, timeout_ms=60_000):
    """Re-enter the current password when Google asks before password settings."""
    enter_google_password(page, password, timeout_ms)
    next_button = visible_locator(page, PASSWORD_NEXT_SELECTORS, timeout_ms)
    if next_button is None:
        raise RuntimeError("重新验证页未找到 Next 按钮")

    next_button.click(timeout=timeout_ms)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        error = visible_text(page, PASSWORD_ERROR_SELECTORS)
        if error:
            raise RuntimeError(f"Google 重新验证失败: {error}")

        current_url = page.url
        parsed = urlparse(current_url)
        if (parsed.hostname == "myaccount.google.com"
                and "/signinoptions/password" in parsed.path):
            return {"status": "password_settings", "url": current_url}
        if (parsed.hostname == "accounts.google.com"
                and "/challenge/" in parsed.path
                and "/challenge/pwd" not in parsed.path):
            return {"status": "challenge", "url": current_url}
        time.sleep(0.25)

    raise RuntimeError(
        "已完成 Google 密码重新验证，但未进入密码设置页，"
        f"当前地址: {page.url}"
    )


def first_visible_now(page, selectors):
    """Return a visible locator immediately, without a polling timeout."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible():
                return locator
        except Exception:
            continue
    return None


def password_change_fields(page, timeout_ms=60_000):
    """Find the new/confirm password fields across Google Account layouts."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        new_input = first_visible_now(page, NEW_PASSWORD_INPUT_SELECTORS)
        confirm_input = first_visible_now(page, CONFIRM_PASSWORD_INPUT_SELECTORS)
        if new_input is not None and confirm_input is not None:
            return new_input, confirm_input

        candidates = page.locator('input[type="password"]')
        visible = []
        try:
            count = candidates.count()
        except Exception:
            count = 0
        for index in range(count):
            candidate = candidates.nth(index)
            try:
                if candidate.is_visible():
                    visible.append(candidate)
            except Exception:
                continue
        if len(visible) >= 2:
            return visible[0], visible[1]
        time.sleep(0.2)
    raise RuntimeError("未找到 New password 和 Confirm new password 输入框")


def enter_new_google_password(page, new_password, timeout_ms=60_000):
    """Fill and verify both fields on Google's password-change form."""
    new_input, confirm_input = password_change_fields(page, timeout_ms)
    human_type(new_input, new_password)
    human_type(confirm_input, new_password)
    try:
        actual_new = new_input.input_value(timeout=2_000)
        actual_confirm = confirm_input.input_value(timeout=2_000)
    except Exception as exc:
        raise RuntimeError("无法校验 Google 新密码输入框内容") from exc
    if actual_new != new_password or actual_confirm != new_password:
        raise RuntimeError("Google 新密码或确认密码输入不完整")
    return len(new_password)


def submit_google_password_change(page, timeout_ms=60_000):
    """Click Change password and verify navigation or a success message."""
    button = visible_locator(page, CHANGE_PASSWORD_BUTTON_SELECTORS, timeout_ms)
    if button is None:
        raise RuntimeError("未找到 Change password 按钮")

    start_url = page.url
    previous_error = visible_text(page, PASSWORD_CHANGE_ERROR_SELECTORS)
    button.click(timeout=timeout_ms)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        current_url = page.url
        if current_url != start_url:
            return {"status": "changed", "url": current_url}

        success = visible_text(page, PASSWORD_CHANGE_SUCCESS_SELECTORS)
        if success:
            return {"status": "changed", "url": current_url}

        error = visible_text(page, PASSWORD_CHANGE_ERROR_SELECTORS)
        if error and error != previous_error:
            raise RuntimeError(f"Google 拒绝修改密码: {error}")

        form_button = first_visible_now(page, CHANGE_PASSWORD_BUTTON_SELECTORS)
        fields = first_visible_now(page, NEW_PASSWORD_INPUT_SELECTORS)
        if form_button is None and fields is None:
            return {"status": "changed", "url": current_url}
        time.sleep(0.25)

    raise RuntimeError(
        "已点击 Change password，但未确认修改成功，"
        f"当前地址: {page.url}"
    )


def resolve_password(args, parser):
    """Resolve a password from CLI, environment, or a hidden prompt."""
    if args.password is not None:
        print(
            "[warn] --password 可能暴露在命令历史和进程列表中；"
            "建议改用 --ask-password"
        )
        return args.password
    if args.password_env:
        password = os.environ.get(args.password_env)
        if password is None:
            parser.error(f"环境变量 {args.password_env!r} 未设置")
        return password
    if args.ask_password:
        return getpass.getpass("Google password: ")
    return None


def resolve_new_password(args, parser):
    """Resolve the replacement password without storing it in source code."""
    if args.new_password is not None:
        print(
            "[warn] --new-password 可能暴露在命令历史和进程列表中；"
            "建议改用 --ask-new-password"
        )
        return args.new_password
    if args.new_password_env:
        password = os.environ.get(args.new_password_env)
        if password is None:
            parser.error(f"环境变量 {args.new_password_env!r} 未设置")
        return password
    if args.ask_new_password:
        password = getpass.getpass("New Google password: ")
        confirmation = getpass.getpass("Confirm new Google password: ")
        if password != confirmation:
            parser.error("两次输入的新密码不一致")
        return password
    return None


def run_google_setup(
        client, args, browser_name, email=None, password=None, new_password=None,
        close_when_done=False, keep_open_on_error=False):
    """Run the Google setup flow for one BitBrowser window."""
    profile_id = None
    try:
        profiles = client.list_browsers(name=browser_name)
        profile = find_profile_by_name(profiles, browser_name)
        profile_id = profile["id"]
        already_open = client.is_open(profile_id)
        if new_password is not None:
            total_steps = 12
        else:
            total_steps = 10 if password is not None else (6 if email else 4)
        print(
            f"[1/{total_steps}] {'接管已打开' if already_open else '打开'}窗口 "
            f"{browser_name!r} ({profile_id})"
        )
        cdp_url = client.open_browser(profile_id)
    except requests.RequestException as exc:
        print(f"[error] 比特浏览器 Local API 请求失败: {exc}", file=sys.stderr)
        return False
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return False

    succeeded = False
    completed = False
    try:
        print(f"[2/{total_steps}] 连接浏览器 CDP")
        playwright_manager, playwright = start_sync_playwright()
        try:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                raise RuntimeError("浏览器没有可用的 context")
            page = choose_page(browser.contexts[0])

            print(f"[3/{total_steps}] 在 Google 搜索 {args.query!r}")
            result_url = search_google(
                page,
                query=args.query,
                timeout_ms=args.timeout * 1000,
            )
            print(f"      结果页: {result_url}")

            print(f"[4/{total_steps}] 点击 Google Sign in")
            login_url = click_google_sign_in(
                page,
                timeout_ms=args.timeout * 1000,
            )
            print(f"      登录页: {login_url}")

            if email:
                print(f"[5/{total_steps}] 输入 Google 邮箱 {email!r}")
                enter_google_email(
                    page,
                    email,
                    timeout_ms=args.timeout * 1000,
                )
                print(f"[6/{total_steps}] 点击 Next")
                password_url = click_identifier_next(
                    page,
                    timeout_ms=args.timeout * 1000,
                )
                print(f"完成，已进入密码页: {password_url}")
                if password is None:
                    completed = True
                if password is not None:
                    print(f"[7/{total_steps}] 输入 Google 密码")
                    enter_google_password(
                        page,
                        password,
                        timeout_ms=args.timeout * 1000,
                    )
                    print(f"[8/{total_steps}] 点击密码页 Next")
                    login_result = click_password_next(
                        page,
                        timeout_ms=args.timeout * 1000,
                    )
                    if login_result["status"] == "workspace_terms":
                        print("检测到 Workspace 首次登录条款页")
                        print(
                            f"[9/{total_steps}] 点击 I understand "
                            f"（最多等待 {args.terms_timeout} 秒）"
                        )
                        login_result = click_i_understand(
                            page,
                            timeout_ms=args.terms_timeout * 1000,
                        )

                    if login_result["status"] in ("signed_in", "terms_timeout"):
                        if login_result["status"] == "signed_in":
                            print(f"Google 登录成功: {login_result['url']}")
                        else:
                            print(
                                "I understand 点击后等待超时，"
                                "直接进入 Google 密码修改流程"
                            )
                        print(f"[10/{total_steps}] 点击 Google password")
                        settings_result = open_google_password_settings(
                            page,
                            timeout_ms=args.timeout * 1000,
                        )
                        if settings_result["status"] == "reauth":
                            print(
                                "Google 要求重新验证当前密码，自动输入当前密码继续"
                            )
                            settings_result = complete_google_password_reauth(
                                page,
                                password,
                                timeout_ms=args.timeout * 1000,
                            )

                        if settings_result["status"] == "password_settings":
                            print(
                                "已进入 Google 密码设置页: "
                                f"{settings_result['url']}"
                            )
                            if new_password is not None:
                                print(f"[11/{total_steps}] 填写并确认新密码")
                                enter_new_google_password(
                                    page,
                                    new_password,
                                    timeout_ms=args.timeout * 1000,
                                )
                                print(f"[12/{total_steps}] 点击 Change password")
                                change_result = submit_google_password_change(
                                    page,
                                    timeout_ms=args.timeout * 1000,
                                )
                                print(
                                    "Google 密码修改成功: "
                                    f"{change_result['url']}"
                                )
                                completed = True
                            else:
                                completed = True
                        else:
                            print(
                                "Google 要求额外验证，窗口已停留在挑战页: "
                                f"{settings_result['url']}"
                            )
                    else:
                        print(
                            "Google 要求额外验证，窗口已停留在挑战页: "
                            f"{login_result['url']}"
                        )
            else:
                print("完成，未提供 --email，尚未填写账号。")
                completed = True

            if not completed:
                raise RuntimeError("Google 自动化流程未完成，需要人工检查当前页面")

            succeeded = True
            if close_when_done:
                print("流程结束，准备关闭比特浏览器窗口。")
            elif password is None:
                print("比特浏览器窗口保持打开，尚未输入密码。")
            else:
                print("比特浏览器窗口保持打开。")
            # Exiting the Playwright connection does not call BitBrowser /close.
        finally:
            playwright_manager.__exit__()
    except Exception as exc:
        print(f"[error] 浏览器操作失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        if close_when_done and not keep_open_on_error:
            print("本轮失败，仍按批量模式关闭窗口继续下一个。", file=sys.stderr)
        else:
            print("窗口保持打开，便于人工检查。", file=sys.stderr)
        return False
    finally:
        if close_when_done and profile_id and (succeeded or not keep_open_on_error):
            client.close_browser(profile_id)
    return True


def run_batch(client, args, parser):
    """Run Google setup over a mail file and sequential BitBrowser names."""
    try:
        accounts = load_mail_file(args.file)
        browser_names = browser_name_sequence(args.browser_name, len(accounts))
    except ValueError as exc:
        parser.error(str(exc))

    print(f"邮箱文件有效记录: {len(accounts)} 条")
    print(f"起始窗口: {args.browser_name}")
    print(f"统一新密码: 使用脚本内置值")
    print("每个窗口操作结束后会自动关闭，再打开下一个。\n")

    succeeded = []
    failed = []
    for index, (account, browser_name) in enumerate(
            zip(accounts, browser_names), start=1):
        print(
            f"== [{index}/{len(accounts)}] 第 {account['line']} 行 "
            f"{browser_name} / {account['email']} =="
        )
        ok = run_google_setup(
            client,
            args,
            browser_name=browser_name,
            email=account["email"],
            password=account["password"],
            new_password=DEFAULT_NEW_PASSWORD,
            close_when_done=True,
            keep_open_on_error=args.keep_open_on_error,
        )
        if ok:
            succeeded.append((browser_name, account["email"]))
        else:
            failed.append((browser_name, account["email"], account["line"]))
        print()

    print("批量邮箱登录/改密完成")
    print(f"成功={len(succeeded)} 失败={len(failed)}")
    if failed:
        print("\n失败记录:")
        for browser_name, email, line_number in failed:
            print(f"  第 {line_number} 行 {browser_name}: {email}")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="按窗口名打开比特浏览器，进入 Google 登录页并填写邮箱",
    )
    parser.add_argument(
        "--browser-name",
        required=True,
        help="比特浏览器窗口名称；批量模式下作为起始窗口，例如 tiktok_25",
    )
    parser.add_argument(
        "--file",
        help="批量邮箱文件，每行格式：账号----密码----可忽略备注",
    )
    parser.add_argument(
        "--query",
        default="gmail",
        help="Google 搜索词，默认 gmail",
    )
    parser.add_argument(
        "--email",
        help="可选的 Google 邮箱；填写后点击 Next 并停留在密码页",
    )
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--password",
        help="Google 密码；不推荐，会出现在命令历史和进程参数中",
    )
    password_group.add_argument(
        "--password-env",
        metavar="ENV_NAME",
        help="从指定环境变量读取 Google 密码",
    )
    password_group.add_argument(
        "--ask-password",
        action="store_true",
        help="在终端隐藏输入 Google 密码（推荐）",
    )
    new_password_group = parser.add_mutually_exclusive_group()
    new_password_group.add_argument(
        "--new-password",
        help="要设置的新密码；不推荐，会出现在命令历史和进程参数中",
    )
    new_password_group.add_argument(
        "--new-password-env",
        metavar="ENV_NAME",
        help="从指定环境变量读取要设置的新密码",
    )
    new_password_group.add_argument(
        "--ask-new-password",
        action="store_true",
        help="在终端隐藏输入并确认新密码（推荐）",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:54345",
        help="比特浏览器 Local API 地址",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="页面操作超时秒数，默认 60",
    )
    parser.add_argument(
        "--terms-timeout",
        type=int,
        default=60,
        help="点击 I understand 后的等待秒数，默认 60；超时后继续密码流程",
    )
    parser.add_argument(
        "--keep-open-on-error",
        action="store_true",
        help="批量模式失败时保留当前窗口，默认失败也关闭窗口继续下一个",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    if args.terms_timeout <= 0:
        parser.error("--terms-timeout 必须大于 0")
    client = BitBrowserClient(args.api_url)
    if args.file:
        if args.email:
            parser.error("批量模式从 --file 读取账号，请勿传 --email")
        if args.password is not None or args.password_env or args.ask_password:
            parser.error("批量模式从 --file 读取当前密码，请勿传 --password")
        if (args.new_password is not None
                or args.new_password_env
                or args.ask_new_password):
            parser.error("批量模式统一使用脚本内置新密码，请勿传 --new-password")
        return run_batch(client, args, parser)

    password = resolve_password(args, parser)
    new_password = resolve_new_password(args, parser)
    if new_password is None and password is not None:
        new_password = DEFAULT_NEW_PASSWORD
    if password is not None and not args.email:
        parser.error("提供密码时必须同时提供 --email")
    if password == "":
        parser.error("Google 密码不能为空")
    if new_password is not None and password is None:
        parser.error("修改密码时必须同时提供当前密码")
    if new_password == "":
        parser.error("Google 新密码不能为空")
    if new_password is not None and len(new_password) < 8:
        parser.error("Google 新密码至少需要 8 个字符")
    if new_password is not None and new_password == password:
        parser.error("Google 新密码不能与当前密码相同")

    ok = run_google_setup(
        client,
        args,
        browser_name=args.browser_name,
        email=args.email,
        password=password,
        new_password=new_password,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
