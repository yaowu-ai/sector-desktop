"""Bounded page and control checks used only by target-account engagement."""
import re
from urllib.parse import urljoin, urlsplit

from platforms.tiktok.navigation import is_retryable_tiktok_navigation_error

NAVIGATION_TIMEOUT_MS = 30000
RECOVERY_POLLS = 3
RECOVERY_WAIT_MS = 2000
MAX_PROFILE_SCROLLS = 3
LIKE_SELECTOR = (
    '[data-e2e="like-icon"], [data-e2e="browse-like-icon"], '
    'button[aria-label*="like" i], button[aria-label*="赞"], '
    'button[aria-label*="讚"], button[aria-label*="喜欢"]'
)
FOLLOW_NAME = re.compile(
    r"^(follow|following|unfollow|friends|requested|关注|已关注|取消关注|互相关注|已请求|關注|已關注)[\s✓✔]*$",
    re.I,
)


def target_url_matches(url, handle, video_id=None):
    try:
        parsed = urlsplit(str(url or ""))
        path = f"/@{str(handle).strip().lstrip('@')}"
        if video_id is not None:
            path += f"/video/{video_id}"
        return (
            parsed.scheme in {"http", "https"}
            and parsed.netloc.lower() in {"tiktok.com", "www.tiktok.com"}
            and parsed.path.rstrip("/").casefold() == path.casefold()
        )
    except ValueError:
        return False


def visible_items(locator, limit=12):
    return [item for i in range(min(locator.count(), limit))
            if (item := locator.nth(i)).is_visible()]


def unique_visible(locator):
    items = visible_items(locator)
    return items[0] if len(items) == 1 else None


def profile_title(page, handle):
    if not target_url_matches(page.url, handle):
        return None
    titles = page.locator('[data-e2e="user-title"], h1, h2')
    expected = str(handle).strip().lstrip("@").casefold()
    for title in visible_items(titles, limit=8):
        if title.inner_text(timeout=500).strip().lstrip("@").casefold() == expected:
            return title
    return None


def profile_follow_button(page, handle):
    """Search near the matching profile title; never choose a suggested account."""
    root = profile_title(page, handle)
    if root is None:
        return None
    title_box = root.bounding_box(timeout=500)
    for _ in range(5):
        root = root.locator("xpath=..")
        buttons = root.locator('[data-e2e="follow-button"], [data-e2e="following-button"]')
        matches = visible_items(buttons)
        if not matches:
            matches = visible_items(root.get_by_role("button", name=FOLLOW_NAME))
        if matches:
            if len(matches) != 1:
                return None
            button_box = matches[0].bounding_box(timeout=500)
            # Suggested-account cards sit below the profile's own action row.
            if title_box and button_box and abs(button_box["y"] - title_box["y"]) < 200:
                return matches[0]
            return None
    return None


def video_control_scope(page):
    """Use the visible player's nearest action container, not the recommendations."""
    videos = visible_items(page.locator("video"), limit=6)
    viewport = page.viewport_size or {"width": 1280, "height": 800}
    for video in videos:
        box = video.bounding_box(timeout=500)
        if not box or box["y"] >= viewport["height"] or box["y"] + box["height"] <= 0:
            continue
        root = video
        for _ in range(7):
            root = root.locator("xpath=..")
            if root.evaluate("el => ['BODY', 'HTML'].includes(el.tagName)"):
                break
            if visible_items(root.locator(LIKE_SELECTOR)):
                return root
    return None


def target_like_button(page):
    root = video_control_scope(page)
    if root is None:
        return None
    # Prefer video-specific icons over generic text such as 'You may like'.
    icon = unique_visible(root.locator('[data-e2e="like-icon"], [data-e2e="browse-like-icon"]'))
    if icon is not None:
        button = icon.locator('xpath=ancestor-or-self::*[self::button or @role="button"][1]')
        return button.first if button.count() else icon
    return unique_visible(root.locator(LIKE_SELECTOR))


def target_like_click_point(control, point=None):
    """Hit-test the pinned node at its visible centre or at a prepared point."""
    return control.evaluate("""(el, point) => {
      if (!el.isConnected) return null;
      const style = getComputedStyle(el);
      if (style.visibility !== 'visible' || style.display === 'none' ||
          style.pointerEvents === 'none') return null;
      const rect = el.getBoundingClientRect();
      const left = Math.max(0, rect.left), right = Math.min(innerWidth, rect.right);
      const top = Math.max(0, rect.top), bottom = Math.min(innerHeight, rect.bottom);
      if (left >= right || top >= bottom) return null;
      const x = point ? point.x : (left + right) / 2;
      const y = point ? point.y : (top + bottom) / 2;
      if (x < left || x >= right || y < top || y >= bottom) return null;
      const hit = document.elementFromPoint(x, y);
      return hit && (hit === el || el.contains(hit)) ? {x, y} : null;
    }""", point)


def toggle_state(button, kind):
    """Return True/False/None; unreadable or conflicting state never permits a click."""
    snapshot = button.evaluate("""el => {
      const selector = '[data-e2e="like-icon"], [data-e2e="browse-like-icon"]';
      const heart = el.matches(selector) ? el : el.querySelector(selector);
      return {
        pressed: el.getAttribute('aria-pressed'),
        label: (el.getAttribute('aria-label') || '').trim(),
        text: (el.innerText || '').trim(),
        marker: el.getAttribute('data-e2e') || '',
        fills: Array.from(el.querySelectorAll('svg, svg path')).slice(0, 8)
          .map(node => getComputedStyle(node).fill.toLowerCase().replace(/\\s/g, '')),
        heart_fills: heart ? Array.from(heart.querySelectorAll('svg, path, use')).slice(0, 8)
          .map(node => getComputedStyle(node).fill.toLowerCase().replace(/\\s/g, '')) : []
      };
    }""")
    yes, no = False, False
    label = snapshot["label"].casefold()
    pressed = snapshot["pressed"]
    if pressed in {"true", "false"}:
        yes, no = pressed == "true", pressed == "false"
    if kind == "like":
        yes |= bool(re.fullmatch(r"(unlike|remove like|取消点赞|取消讚|取消喜欢|取消喜歡)", label))
        no |= bool(re.fullmatch(r"(like|like video|点赞|讚|喜欢|喜歡)", label))
        fills = snapshot["fills"]
        red = any(fill in {"rgb(254,44,85)", "rgb(255,44,85)", "rgb(255,59,92)",
                           "#fe2c55", "#ff2c55", "#ff3b5c"} for fill in fills)
        yes |= red
        # Generic white SVGs can belong to comment/share controls or to an
        # unrecognised heart variant; only the identified heart proves unliked.
        heart_fills = snapshot.get("heart_fills", [])
        if (not yes and not no and heart_fills
                and all(fill in {"rgb(255,255,255)", "#ffffff", "none", "rgba(0,0,0,0)"}
                        for fill in heart_fills)
                and any(fill in {"rgb(255,255,255)", "#ffffff"} for fill in heart_fills)):
            no = True
    else:
        text = re.sub(r"[\s✓✔]+", "", snapshot["text"].casefold())
        values = {label, text}
        yes |= bool(values & {"following", "unfollow", "friends", "requested", "已关注", "已關注", "取消关注", "互相关注", "已请求"})
        yes |= snapshot["marker"] == "following-button"
        no |= bool(values & {"follow", "关注", "關注"})
    return None if yes == no else yes


def target_page_state(page, handle, video_id=None):
    if not target_url_matches(page.url, handle, video_id):
        return False, "url_mismatch"
    try:
        if video_id is None:
            return (True, "ok") if profile_title(page, handle) is not None else (False, "profile_not_ready")
        for video in visible_items(page.locator("video"), limit=6):
            if video.evaluate("""el => {
                const box = el.getBoundingClientRect();
                return box.bottom > 0 && box.top < innerHeight &&
                    box.right > 0 && box.left < innerWidth && el.readyState >= 2 && !el.error;
            }"""):
                return True, "ok"
        return False, "video_not_ready"
    except Exception:
        return False, "page_check_failed"


def recover_target_page(page, handle, video_id=None):
    """Extra waits and one reload apply only when the requested page is not ready."""
    ready, reason = target_page_state(page, handle, video_id)
    if ready or reason == "url_mismatch":
        return ready, reason
    try:
        text = page.locator("body").inner_text(timeout=1000)[:2000].casefold()
        if any(marker in text for marker in ("verify you are human", "security verification", "captcha", "请完成验证")):
            return False, "verification_required"
        maintenance = "something went wrong" in text or "site maintenance" in page.title().casefold()
        for reload in (False, True):
            if reload:
                page.reload(wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            for _ in range(RECOVERY_POLLS):
                page.wait_for_timeout(RECOVERY_WAIT_MS)
                ready, reason = target_page_state(page, handle, video_id)
                if ready or reason == "url_mismatch":
                    return ready, reason
        return False, "maintenance_page" if maintenance else reason
    except Exception:
        return False, "page_recovery_failed"


def navigate_target_page(page, handle, video_id=None):
    url = f"https://www.tiktok.com/@{str(handle).strip().lstrip('@')}"
    if video_id is not None:
        url += f"/video/{video_id}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    except Exception as exc:
        if not is_retryable_tiktok_navigation_error(exc):
            return False, "navigation_failed"
        # A timeout may already have committed the desired page. Inspect it first.
        if not target_url_matches(page.url, handle, video_id):
            return False, "navigation_failed"
    return recover_target_page(page, handle, video_id)


def video_link_id(href, handle):
    url = urljoin("https://www.tiktok.com", str(href or ""))
    try:
        match = re.fullmatch(r"/@[^/]+/video/(\d+)/?", urlsplit(url).path)
    except ValueError:
        return None
    return match.group(1) if match and target_url_matches(url, handle, match.group(1)) else None
