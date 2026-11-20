"""Daily engagement on target TikTok accounts' new videos."""
import random
import re
import time

from human_mouse import MouseState, human_click_locator
from platforms.tiktok.actions import (
    choose_comment_text,
    human_pause,
    log_comment_source_event,
)
from platforms.tiktok.video_info import capture_active_video_info
from platforms.tiktok.target_page import (
    MAX_PROFILE_SCROLLS, navigate_target_page, profile_follow_button,
    recover_target_page, target_like_button, target_like_click_point, target_page_state,
    target_url_matches, toggle_state, unique_visible, video_link_id,
)

COMMENTS_NAME = re.compile(r"^(Comments|评论|評論)(?:\s*\(?\d+\)?)?$", re.I)


def _video_id_from_href(href):
    """Extract a TikTok video id from a profile href."""
    m = re.search(r"/video/(\d+)", href or "")
    return m.group(1) if m else None


def fetch_recent_videos(page, handle, max_items=12, scan_limit=60):
    """Recent video ids on @handle's profile, newest-first by snowflake id."""
    if not target_url_matches(page.url, handle):
        opened, reason = navigate_target_page(page, handle)
        if not opened:
            raise RuntimeError(f"target_profile_open_failed reason={reason}")

    # Following can insert a suggested-accounts row above the video grid.
    tab = unique_visible(page.get_by_role("tab", name=re.compile(r"^(Videos|视频|影片)$", re.I)))
    if tab is None:
        tab = unique_visible(page.get_by_text(re.compile(r"^(Videos|视频|影片)$", re.I)))
    if tab is not None:
        tab.scroll_into_view_if_needed(timeout=2000)
        tab.click(timeout=2000)

    for attempt in range(MAX_PROFILE_SCROLLS + 1):
        anchors = page.locator('a[href*="/video/"]')
        seen = set()
        for i in range(min(anchors.count(), scan_limit)):
            try:
                vid = video_link_id(anchors.nth(i).get_attribute("href", timeout=500), handle)
                if vid:
                    seen.add(vid)
            except Exception:
                continue
        if seen:
            return sorted(seen, key=int, reverse=True)[:max_items]
        if attempt < MAX_PROFILE_SCROLLS:
            viewport = page.viewport_size or {"width": 1280, "height": 800}
            page.mouse.move(viewport["width"] // 2, viewport["height"] // 2)
            page.mouse.wheel(0, int(viewport["height"] * 0.75))
            page.wait_for_timeout(800)
    return []


def follow_target_profile(page, handle):
    """Follow @handle from its profile page once."""
    if not target_url_matches(page.url, handle):
        opened, _ = navigate_target_page(page, handle)
        if not opened:
            return "unknown"
    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)
    btn = profile_follow_button(page, handle)
    if btn is None:
        return "unknown"
    state = toggle_state(btn, "follow")
    if state is True:
        return "already"
    if state is None:
        return "unknown"
    btn.scroll_into_view_if_needed(timeout=2000)
    if not btn.is_enabled() or toggle_state(btn, "follow") is not False:
        return "unknown"
    if not human_click_locator(page, btn, mouse_state):
        return "fail"
    human_pause(0.6, 1.5)
    btn = profile_follow_button(page, handle)
    if btn is not None and toggle_state(btn, "follow") is True:
        return "followed"
    return "fail"


def _target_video_open_state(page, handle, video_id):
    """Confirm navigation landed on the requested target video before actions."""
    return target_page_state(page, handle, video_id)


def _like_target_video(page, mouse_state, *, attempted_likes=None, video_key=None):
    if attempted_likes is not None and video_key in attempted_likes:
        return False, "already_attempted", False
    btn = target_like_button(page)
    if btn is None:
        return False, "button_not_found", False
    control = None
    attempted = False
    try:
        # Pin the original node: a re-render must not retarget a fresh locator.
        control = btn.element_handle(timeout=1000)
        if control is None:
            return False, "button_not_found", False
        state = toggle_state(control, "like")
        if state is True:
            return False, "already_liked", False
        if state is None or not control.is_enabled():
            return False, "state_unknown", False
        original_url = page.url
        control.scroll_into_view_if_needed(timeout=1000)
        point = target_like_click_point(control)
        if point is None:
            return False, "target_not_interactable", False
        page.mouse.move(point["x"], point["y"])
        mouse_state.update(point["x"], point["y"])
        state = toggle_state(control, "like")
        if state is True:
            return False, "already_liked", False
        if state is None or not control.is_enabled():
            return False, "state_unknown", False
        if page.url != original_url or target_like_click_point(control, point) is None:
            return False, "target_changed", False
        if attempted_likes is not None:
            attempted_likes.add(video_key)
        attempted = True
        # Mouse down/up each send one protocol command, without locator.click's
        # action retry loop. Always release once, even if down's acknowledgement
        # is lost; never send a second press to compensate for an uncertain result.
        try:
            page.mouse.down(button="left")
        finally:
            page.mouse.up(button="left")
    except Exception:
        return False, "click_unconfirmed" if attempted else "preparation_failed", attempted
    finally:
        if control is not None:
            try:
                control.dispose()
            except Exception:
                pass
    human_pause(0.5, 1.0)
    btn = target_like_button(page)
    liked = btn is not None and toggle_state(btn, "like") is True
    return liked, "liked" if liked else "state_unconfirmed", True


def _comment_on_video_page(page, mouse_state, text):
    """Type and post a comment on an open /video/ page."""
    tab = unique_visible(page.get_by_role("tab", name=COMMENTS_NAME))
    if tab is None:
        tab = unique_visible(page.get_by_text(COMMENTS_NAME))
    if tab is not None and tab.get_attribute("aria-selected") != "true":
        tab.click(timeout=2000)
    editors = page.locator(
        '[data-e2e="comment-input"] [contenteditable="true"], '
        '[data-e2e="comment-input"][contenteditable="true"], '
        'textarea[placeholder*="comment" i], textarea[placeholder*="评论"], '
        'textarea[placeholder*="評論"]'
    )
    try:
        editors.first.wait_for(state="visible", timeout=2500)
    except Exception:
        return False
    box = unique_visible(editors)
    if box is None:
        return False
    # Do not overwrite an existing draft or submit to an unrelated editor.
    if (box.input_value() if box.evaluate("el => el.tagName === 'TEXTAREA'")
            else box.inner_text(timeout=500)).strip():
        return False
    human_pause(0.4, 1.0)
    try:
        # Element-bound input avoids page-level key events reaching video shortcuts
        # when the comment editor loses focus during typing.
        box.fill(text, timeout=2500)
        focused = box.evaluate("el => el === document.activeElement || el.contains(document.activeElement)")
        typed = box.input_value() if box.evaluate("el => el.tagName === 'TEXTAREA'") else box.inner_text(timeout=500)
        if not focused or typed.strip() != text.strip():
            return False
    except Exception:
        return False
    human_pause(0.6, 1.5)
    post = unique_visible(page.locator('[data-e2e="comment-post"]'))
    if post is not None:
        if post.get_attribute("aria-disabled") == "true" or not post.is_enabled():
            return False
        # An uncertain click must never be followed by a second submission.
        try:
            post.click(timeout=2000)
        except Exception:
            return False
    else:
        box.press("Enter", timeout=2000)
    human_pause(1.0, 2.0)
    try:
        remaining = box.input_value() if box.evaluate("el => el.tagName === 'TEXTAREA'") else box.inner_text(timeout=500)
        return not remaining.strip()
    except Exception:
        return False


def engage_target_video(
    page, handle, video_id, comment_pool, like_prob=0.9, comment_prob=0.5,
    *, ai_comment_config=None, conn=None, platform="tiktok", account_id=None,
    attempted_likes=None,
):
    """Open one target video, watch a while, then maybe like/comment."""
    opened, open_reason = _open_target_video(page, handle, video_id)
    if not opened:
        return {
            "opened": False,
            "open_reason": open_reason,
            "liked": False,
            "like_attempted": False,
            "like_reason": "not_attempted",
            "commented": False,
            "comment_attempted": False,
        }

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    time.sleep(random.uniform(5, 15))

    if not target_url_matches(page.url, handle, video_id):
        return {"opened": False, "open_reason": "video_changed", "liked": False, "commented": False}

    liked = False
    like_attempted = False
    like_reason = "not_attempted"
    if random.random() < like_prob:
        liked, like_reason, like_attempted = _like_target_video(
            page, mouse_state, attempted_likes=attempted_likes,
            video_key=(platform, account_id, str(video_id)),
        )
        human_pause(0.5, 1.5)

    commented = False
    comment_attempted = False
    ai_comment_config = ai_comment_config or {}
    ai_enabled = bool(ai_comment_config.get("enabled"))
    if ((comment_pool or ai_enabled) and random.random() < comment_prob
            and target_url_matches(page.url, handle, video_id)):
        video_info = capture_active_video_info(page) if ai_enabled else {}
        text, source_event = choose_comment_text(comment_pool, video_info, ai_comment_config, platform)
        log_comment_source_event(conn, platform, account_id, source_event)
        # Generation may take a few seconds; never submit onto a different video.
        if text and target_url_matches(page.url, handle, video_id):
            comment_attempted = True
            commented = _comment_on_video_page(page, mouse_state, text)
            human_pause(1.0, 2.5)

    if liked and comment_attempted:
        btn = target_like_button(page) if target_url_matches(page.url, handle, video_id) else None
        final_state = toggle_state(btn, "like") if btn is not None else None
        if final_state is not True:
            liked = False
            like_reason = ("state_reverted_after_comment" if final_state is False
                           else "state_unconfirmed_after_comment")

    return {
        "opened": True,
        "liked": liked,
        "like_attempted": like_attempted,
        "like_reason": like_reason,
        "commented": commented,
        "comment_attempted": comment_attempted,
    }


def _open_target_video(page, handle, video_id):
    if target_url_matches(page.url, handle):
        anchors = page.locator('a[href*="/video/"]')
        for i in range(min(anchors.count(), 60)):
            link = anchors.nth(i)
            if video_link_id(link.get_attribute("href", timeout=500), handle) != str(video_id):
                continue
            try:
                link.scroll_into_view_if_needed(timeout=2000)
                # Keep the session on its existing page even for target=_blank links.
                if link.get_attribute("target") == "_blank":
                    return navigate_target_page(page, handle, video_id)
                link.click(timeout=3000)
                human_pause(3, 6)
                if target_url_matches(page.url, handle, video_id):
                    return recover_target_page(page, handle, video_id)
            except Exception:
                pass
            break
    return navigate_target_page(page, handle, video_id)
