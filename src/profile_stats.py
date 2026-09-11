"""Read Following / Followers / Likes from a TikTok profile via CDP."""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urljoin, urlsplit

from profile_activity import read_activity


DEFAULT_TIMEOUT = 30
COUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*[KMB万亿]?"
STATS = re.compile(
    rf"^\s*(?P<following>{COUNT})\s+Following\s+"
    rf"(?P<followers>{COUNT})\s+Followers\s+"
    rf"(?P<likes>{COUNT})\s+Likes\s*$",
    re.IGNORECASE,
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_timeout(timeout):
    timeout = int(timeout)
    if timeout <= 0:
        raise ValueError("timeout 必须是正数")
    return timeout


def account_field(account, key, default=None):
    if isinstance(account, dict):
        return account.get(key, default)
    return getattr(account, key, default)


def collection_error(exc):
    return f"{type(exc).__name__}: {exc}"


def parse_stats(text):
    """Parse the profile's English statistics heading; never default to zero.

    Abbreviated counts are estimates of the displayed rounded value.
    """
    match = STATS.fullmatch(text)
    if not match:
        raise ValueError("未找到完整的 Following / Followers / Likes 统计")
    raw = {key: value.strip() for key, value in match.groupdict().items()}
    counts = {}
    approximate = []
    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000,
                   "万": 10000, "亿": 100000000}
    for key, value in raw.items():
        number = value.replace(",", "").replace(" ", "").upper()
        multiplier = multipliers.get(number[-1])
        if multiplier:
            approximate.append(key)
            number = number[:-1]
        counts[key] = int(Decimal(number) * (multiplier or 1))
    return {**counts, "raw": raw, "approximate_fields": approximate}


def profile_handle(url):
    parsed = urlsplit(url)
    if parsed.hostname not in {"www.tiktok.com", "tiktok.com"}:
        return None
    match = re.fullmatch(r"/@([A-Za-z0-9._]+)/?", parsed.path)
    return match.group(1).lower() if match else None


def read_stats(page, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # The live profile exposes all three metrics in a single heading.
        headings = page.get_by_role("heading")
        for heading in headings.all():
            if heading.is_visible():
                try:
                    return parse_stats(heading.inner_text(timeout=1000))
                except ValueError:
                    continue
        page.wait_for_timeout(250)
    raise RuntimeError(
        "等待主页统计超时：请确认页面加载完成、语言为英语，且没有登录或验证弹窗。"
    )


def logged_in_handle(page, timeout):
    """Use the account navigation link, never the currently viewed profile."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        links = page.get_by_role(
            "link", name=re.compile(r"^(Profile|个人资料|個人資料)$", re.IGNORECASE),
        )
        handles = set()
        for link in links.all():
            if link.is_visible():
                href = link.get_attribute("href", timeout=1000)
                handle = profile_handle(urljoin(page.url, href or ""))
                if handle:
                    handles.add(handle)
        if len(handles) > 1:
            raise RuntimeError("发现多个不同的个人资料入口，无法确定当前登录账号")
        if handles:
            return handles.pop()
        page.wait_for_timeout(250)
    raise RuntimeError("未识别到当前登录账号：请先登录 TikTok，并确认个人资料入口可见")


class LikedPages:
    """Count a contiguous, deduplicated sequence starting at cursor zero."""

    def __init__(self):
        self.ids = set()
        self.cursor = "0"
        self.complete = False
        self.error = None

    def accept(self, cursor, data):
        if self.complete or str(cursor) != self.cursor:
            return
        if data.get("statusCode") != 0:
            self.error = "liked_request_failed"
            return
        items = data.get("itemList", [])
        more = data.get("hasMore")
        if (not isinstance(items, list) or type(more) is not bool
                or any(not isinstance(item, dict) or not item.get("id") for item in items)):
            self.error = "invalid_liked_response"
            return
        self.ids.update(str(item["id"]) for item in items)
        if not more:
            self.complete = True
        elif data.get("cursor") is None or str(data["cursor"]) == self.cursor:
            self.error = "liked_cursor_not_advancing"
        else:
            self.cursor = str(data["cursor"])

    def result(self):
        return {"liked": len(self.ids) if self.complete else None,
                "liked_loaded": len(self.ids), "liked_complete": self.complete,
                "liked_status": "complete" if self.complete else (self.error or "timeout")}


def read_liked(page, timeout):
    """Observe responses triggered by the Liked UI; never replay private APIs."""
    state = LikedPages()

    def on_response(response):
        url = urlsplit(response.url)
        if url.hostname not in {"www.tiktok.com", "tiktok.com"} or url.path != "/api/favorite/item_list/":
            return
        try:
            cursor = parse_qs(url.query).get("cursor", [None])[0]
            state.accept(cursor, response.json())
        except Exception:
            state.error = "invalid_liked_response"

    page.on("response", on_response)
    try:
        page.get_by_role("tab", name="Liked", exact=True).click(timeout=timeout * 1000)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not state.complete and not state.error:
            # Scrolling the final card also works when TikTok uses an inner scroller.
            cards = page.locator('[data-e2e="user-liked-item"]')
            if cards.count():
                cards.last.scroll_into_view_if_needed(timeout=1000)
                cards.last.hover(timeout=1000)
                page.mouse.wheel(0, 1000)
            page.wait_for_timeout(500)
    except Exception:
        state.error = "liked_ui_unavailable"
    finally:
        page.remove_listener("response", on_response)
    return state.result()


def collect_current_account(browser, timeout):
    timeout = normalize_timeout(timeout)
    if len(browser.contexts) != 1:
        raise RuntimeError("自动识别需要唯一浏览器会话，请连接目标账号对应的浏览器窗口")
    context = browser.contexts[0]
    # Use account navigation, not the viewed profile URL, as the bootstrap hint.
    # Fresh-page checks below still validate the current cookie-backed login.
    handles = set()
    deadline = time.monotonic() + min(timeout, 3)
    for existing in reversed(context.pages):
        if time.monotonic() >= deadline:
            break
        if urlsplit(existing.url).hostname not in {"www.tiktok.com", "tiktok.com"}:
            continue
        try:
            handles.add(logged_in_handle(existing, min(0.5, timeout)))
        except Exception:
            continue  # Closed, loading, or denied tabs have no usable login hint.
    if len(handles) > 1:
        raise RuntimeError("已有 TikTok 标签页显示不同登录账号，请关闭过期标签后重试")
    handle = next(iter(handles), None)
    page = context.new_page()
    try:
        if handle is None:
            page.goto("https://www.tiktok.com/?lang=en-GB",
                      wait_until="domcontentloaded", timeout=timeout * 1000)
            handle = logged_in_handle(page, timeout)
        page.goto(f"https://www.tiktok.com/@{handle}?lang=en-GB",
                  wait_until="domcontentloaded", timeout=timeout * 1000)
        result = read_stats(page, timeout)
        result.update(read_liked(page, timeout))
        result["activity"] = read_activity(page, timeout)
        if profile_handle(page.url) != handle or logged_in_handle(page, timeout) != handle:
            raise RuntimeError("读取期间登录账号或主页地址发生变化，请重试")
        return {"handle": handle, **result, "collected_at": utc_now()}
    finally:
        page.close()


def collect(browser, handle=None, timeout=DEFAULT_TIMEOUT):
    timeout = normalize_timeout(timeout)
    if handle is None:
        return collect_current_account(browser, timeout)
    pages = [page for context in browser.contexts for page in context.pages]
    matches = [page for page in pages if profile_handle(page.url) == handle.lower()]
    if not browser.contexts:
        raise RuntimeError("浏览器没有可用的会话")
    context = matches[-1].context if matches else browser.contexts[0]
    page = context.new_page()
    try:
        page.goto(f"https://www.tiktok.com/@{handle}?lang=en-GB",
                  wait_until="domcontentloaded", timeout=timeout * 1000)
        result = read_stats(page, timeout)
        result.update(read_liked(page, timeout))
        result["activity"] = {"status": "skipped_explicit_handle",
                              "comment_publish_evidence": "not_confirmed"}
        if profile_handle(page.url) != handle.lower():
            raise RuntimeError("页面跳转到了其他地址，未返回该账号的统计")
        return {"handle": handle, **result, "collected_at": utc_now()}
    finally:
        page.close()


def collect_profile_snapshot(browser, account=None, timeout=DEFAULT_TIMEOUT):
    """Collect the current task account snapshot without owning browser cleanup.

    This is the internal entry point intended for TikTok runner integration.
    It reuses the already-open CDP browser, creates only temporary tabs through
    collect(), and returns a stable success/failure envelope for later storage.
    """
    envelope = {
        "account_id": account_field(account, "id"),
        "platform": account_field(account, "platform", "tiktok"),
        "status": "unknown",
        "error": None,
    }
    try:
        result = collect(browser, timeout=timeout)
        return {**envelope, **result, "status": "success", "error": None}
    except Exception as exc:
        return {
            **envelope,
            "status": "failed",
            "error": collection_error(exc),
            "collected_at": utc_now(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cdp", help="Chrome/BitBrowser 的 CDP HTTP 或 WebSocket 地址")
    source.add_argument("--browser-name", help="比特浏览器窗口的完整名称")
    parser.add_argument("--api-url", default="http://127.0.0.1:54345")
    parser.add_argument("--handle", help="可选：指定其他账号（可带 @）；默认读取当前登录账号")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="等待秒数（默认 30）")
    args = parser.parse_args()
    handle = args.handle.removeprefix("@") if args.handle is not None else None
    if (handle is not None and not re.fullmatch(r"[A-Za-z0-9._]+", handle)) or args.timeout <= 0:
        parser.error("用户名格式不正确，或 timeout 不是正数")
    try:
        from patchright_runtime import start_sync_playwright, stop_sync_playwright

        endpoint = args.cdp
        if args.browser_name:
            from bitbrowser import BitBrowserClient

            client = BitBrowserClient(args.api_url)
            profiles = [p for p in client.list_browsers(name=args.browser_name)
                        if p.get("name") == args.browser_name]
            if len(profiles) != 1:
                raise RuntimeError("比特浏览器窗口名称必须精确匹配唯一窗口")
            endpoint = client.open_browser(profiles[0]["id"])
        playwright_manager, playwright = start_sync_playwright()
        try:
            browser = playwright.chromium.connect_over_cdp(
                endpoint, timeout=args.timeout * 1000,
            )
            result = collect(browser, handle, args.timeout)
            # Stop the driver to detach; do not close the user's browser.
        finally:
            cleanup_error = stop_sync_playwright(playwright_manager)
            if cleanup_error:
                print(f"Patchright 清理警告：{cleanup_error}", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
