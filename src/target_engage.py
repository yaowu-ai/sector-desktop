"""Daily engagement on target (brand) accounts' new videos.

Visits a target handle's profile, reads the recent video ids straight from the
grid (no need to open each), and — driven by main.py's watermark logic — opens
the genuinely-new ones to watch / like / comment.

Two primitives are exposed; main.py owns the SQLite watermark + selection:
    fetch_recent_videos(page, handle)              -> [video_id, ...] newest-first
    engage_target_video(page, handle, video_id...) -> {"liked": bool, "commented": bool}

Video ids are TikTok snowflakes: a larger id means a newer post. We sort by id,
so a pinned (but older) video at the top of the grid never reads as "new".
"""
import random
import re
import time

from human_mouse import MouseState, human_click_locator
from actions import (
    try_like,
    human_pause,
    _find_active_button,
    _focus_comment_box,
    _human_type,
    _close_comment_panel,
)


def _video_id_from_href(href):
    """'/@h/video/7412...' or a full URL -> '7412...'; None if no id."""
    m = re.search(r"/video/(\d+)", href or "")
    return m.group(1) if m else None


def fetch_recent_videos(page, handle, max_items=12, scan_limit=60):
    """Recent video ids on @handle's profile, newest-first by snowflake id.

    Reads anchor hrefs from the already-loaded grid (the newest posts sit at the
    top, so no scrolling needed). Returns [] if the profile has no videos.
    """
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
    """Text of the profile's follow/following button, lowercased ('' if none)."""
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
    """Follow @handle from its profile page (once). Returns one of:
        "followed"  verified not-following -> following
        "already"   we already follow it (skip, record so we stop checking)
        "fail"      button not found / no verified state change

    Verification is text/state based (button text -> 'Following', or a
    following-button appears) so it survives data-e2e tweaks, mirroring
    actions.try_follow's "only count a real transition" rule.
    """
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
    # follow button gone after click → treat as success on some layouts
    if page.locator('[data-e2e="follow-button"]').first.count() == 0:
        return "followed"
    return "fail"


def _comment_on_video_page(page, mouse_state, text):
    """Type + post a comment on an open /video/ page. Returns True if posted.

    On the desktop video page the comment column is usually already visible, so
    we go straight for the editor; if no box is found we fall back to clicking the
    comment icon first. Mirrors actions.try_comment's post + verify, but without
    the comment-count gate (brand videos are small, the >1000 rule doesn't apply).
    """
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
        disabled = (post.get_attribute("aria-disabled") in ("true", "")) or \
                   (post.get_attribute("disabled") is not None)
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


def engage_target_video(page, handle, video_id, comment_pool,
                        like_prob=0.9, comment_prob=0.5):
    """Open one target video, watch a while, then maybe like / comment.

    Like and comment fire independently by probability so the 10 participant
    accounts don't all act on every video (reduces the engagement-pod footprint).
    Returns {"liked": bool, "commented": bool}.
    """
    page.goto(f"https://www.tiktok.com/@{handle}/video/{video_id}", timeout=60000)
    human_pause(3, 6)

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    # Watch it — dwell time is a strong trust signal.
    time.sleep(random.uniform(5, 15))

    liked = False
    if random.random() < like_prob:
        liked = try_like(page, mouse_state)
        human_pause(0.5, 1.5)

    commented = False
    if comment_pool and random.random() < comment_prob:
        text = random.choice(comment_pool)
        commented = _comment_on_video_page(page, mouse_state, text)
        human_pause(1.0, 2.5)

    return {"liked": liked, "commented": commented}
