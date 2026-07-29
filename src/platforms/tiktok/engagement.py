"""Daily engagement on target TikTok accounts' new videos."""
import random
import re
import time

from human_mouse import MouseState, human_click_locator
from platforms.tiktok.actions import (
    _close_comment_panel,
    _find_active_button,
    _focus_comment_box,
    _human_type,
    human_pause,
    try_like,
)


def _video_id_from_href(href):
    """Extract a TikTok video id from a profile href."""
    m = re.search(r"/video/(\d+)", href or "")
    return m.group(1) if m else None


def fetch_recent_videos(page, handle, max_items=12, scan_limit=60):
    """Recent video ids on @handle's profile, newest-first by snowflake id."""
    page.goto(f"https://www.tiktok.com/@{handle}", timeout=60000)
    human_pause(3, 5)

    anchors = page.locator('a[href*="/video/"]')
    n = anchors.count()
    seen = set()
    for i in range(min(n, scan_limit)):
        try:
            href = anchors.nth(i).get_attribute("href", timeout=500) or ""
        except Exception:
            continue
        vid = _video_id_from_href(href)
        if vid:
            seen.add(vid)

    ids = sorted(seen, key=lambda x: int(x), reverse=True)
    return ids[:max_items]


def _profile_follow_text(page):
    """Text of the profile's follow/following button, lowercased."""
    btn = page.locator('[data-e2e="follow-button"]').first
    if btn.count() == 0:
        return None
    try:
        return (btn.inner_text(timeout=500) or "").strip().lower()
    except Exception:
        return ""


def _already_following_profile(page):
    """True if the profile clearly shows a following state."""
    if page.locator('[data-e2e="following-button"]').first.count():
        return True
    txt = _profile_follow_text(page)
    return txt is not None and "following" in txt


def follow_target_profile(page, handle):
    """Follow @handle from its profile page once."""
    if f"/@{handle}" not in (page.url or ""):
        page.goto(f"https://www.tiktok.com/@{handle}", timeout=60000)
        human_pause(3, 5)

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    if _already_following_profile(page):
        return "already"

    btn = page.locator('[data-e2e="follow-button"]').first
    if btn.count() == 0:
        return "fail"

    if not human_click_locator(page, btn, mouse_state):
        return "fail"
    human_pause(0.6, 1.5)

    if _already_following_profile(page):
        return "followed"
    if page.locator('[data-e2e="follow-button"]').first.count() == 0:
        return "followed"
    return "fail"


def _comment_on_video_page(page, mouse_state, text):
    """Type and post a comment on an open /video/ page."""
    box = _focus_comment_box(page)
    if box is None:
        icon = _find_active_button(page, '[data-e2e="comment-icon"]')
        if icon is not None:
            human_click_locator(page, icon, mouse_state)
            human_pause(1.5, 3.0)
            box = _focus_comment_box(page)
    if box is None:
        return False

    human_pause(0.4, 1.0)
    _human_type(page, text)
    human_pause(0.6, 1.5)

    posted = False
    post = page.locator('[data-e2e="comment-post"]').first
    if post.count():
        disabled = (post.get_attribute("aria-disabled") in ("true", "")) or (
            post.get_attribute("disabled") is not None
        )
        if not disabled and human_click_locator(page, post, mouse_state):
            posted = True
    if not posted:
        try:
            page.keyboard.press("Enter")
            posted = True
        except Exception:
            posted = False

    human_pause(1.0, 2.0)
    if posted:
        try:
            remaining = (box.inner_text(timeout=500) or "").strip()
            posted = remaining == "" or remaining != text
        except Exception:
            pass
    _close_comment_panel(page)
    return posted


def engage_target_video(page, handle, video_id, comment_pool, like_prob=0.9, comment_prob=0.5):
    """Open one target video, watch a while, then maybe like/comment."""
    page.goto(f"https://www.tiktok.com/@{handle}/video/{video_id}", timeout=60000)
    human_pause(3, 6)

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    time.sleep(random.uniform(5, 15))

    liked = False
    like_attempted = False
    if random.random() < like_prob:
        like_attempted = True
        liked = try_like(page, mouse_state)
        human_pause(0.5, 1.5)

    commented = False
    comment_attempted = False
    if comment_pool and random.random() < comment_prob:
        comment_attempted = True
        text = random.choice(comment_pool)
        commented = _comment_on_video_page(page, mouse_state, text)
        human_pause(1.0, 2.5)

    return {
        "liked": liked,
        "like_attempted": like_attempted,
        "commented": commented,
        "comment_attempted": comment_attempted,
    }
