"""TikTok actions library."""
import random
import time
import uuid

from ai_comment import generate_ai_comment, has_video_context, read_api_key_from_env
from core.runtime import log_action, record_fyp_video_view, update_fyp_video_interactions
from human_mouse import MouseState, human_click_locator
from platforms.tiktok.video_info import capture_active_video_info

LIKE_BUTTON_SELECTORS = (
    'button[aria-label*="Like" i]',
    'button[aria-label*="\u559c\u6b22"]',
    'button[aria-label*="\u8d5e"]',
    'button[aria-label*="\u8b9a"]',
    'button:has([data-e2e="like-icon"])',
    '[data-e2e="like-icon"]',
)


def human_pause(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def _find_active_button(page, selector):
    """Pick the visible button closest to the viewport centre."""
    candidates = page.locator(selector)
    n = candidates.count()
    if n == 0:
        return None

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    vp_center_y = viewport["height"] / 2

    best_idx = None
    best_dist = float("inf")
    for i in range(n):
        btn = candidates.nth(i)
        try:
            box = btn.bounding_box(timeout=500)
        except Exception:
            continue
        if not box:
            continue
        if box["y"] + box["height"] < 0 or box["y"] > viewport["height"]:
            continue
        center_y = box["y"] + box["height"] / 2
        dist = abs(center_y - vp_center_y)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    if best_idx is None:
        return None
    return candidates.nth(best_idx)


def _nearest_button(locator):
    try:
        button = locator.locator("xpath=ancestor-or-self::button[1]").first
        if button.count():
            return button
    except Exception:
        pass
    return locator


def _find_active_like_button(page):
    """Find the active video's like control across TikTok DOM variants."""
    for selector in LIKE_BUTTON_SELECTORS:
        btn = _find_active_button(page, selector)
        if btn is not None:
            return _nearest_button(btn)
    return None


def _scroll_to_next_video(page, viewport, mouse_state):
    """Advance to the next video."""
    if random.random() < 0.75:
        x = random.randint(int(viewport["width"] * 0.3), int(viewport["width"] * 0.7))
        y = random.randint(int(viewport["height"] * 0.3), int(viewport["height"] * 0.7))
        page.mouse.move(x, y, steps=random.randint(8, 20))
        mouse_state.update(x, y)
        human_pause(0.2, 0.7)
        page.mouse.wheel(0, viewport["height"] + random.randint(50, 250))
    else:
        page.keyboard.press("ArrowDown")


def try_like_with_detail(page, mouse_state):
    """Like the visible video. Returns (success, reason)."""
    btn = _find_active_like_button(page)
    if btn is None:
        return False, "button_not_found"

    try:
        if btn.get_attribute("aria-pressed", timeout=500) == "true":
            return False, "already_liked"
    except Exception:
        pass

    if not human_click_locator(page, btn, mouse_state):
        return False, "click_failed"

    time.sleep(random.uniform(0.4, 0.9))

    try:
        btn_after = _find_active_like_button(page)
        if btn_after is None:
            return False, "button_not_found"
        if btn_after.get_attribute("aria-pressed", timeout=500) == "true":
            return True, "liked"
        return False, "state_unchanged"
    except Exception:
        return False, "state_unchanged"


def try_like(page, mouse_state):
    """Like the visible video. Returns True only on a verified state change."""
    success, _reason = try_like_with_detail(page, mouse_state)
    return success


def _follow_icon_d(button):
    """Read the SVG path 'd' attribute on a feed-follow button."""
    try:
        path = button.locator("svg path").first
        if path.count() == 0:
            return ""
        return path.get_attribute("d", timeout=500) or ""
    except Exception:
        return ""


def try_follow(page, mouse_state):
    """Follow the visible video's creator. Verified via SVG path change."""
    btn = _find_active_button(page, '[data-e2e="feed-follow"]')
    if btn is None:
        return False

    d_before = _follow_icon_d(btn)
    if not d_before:
        return False
    if len(d_before) > 200:
        return False

    if not human_click_locator(page, btn, mouse_state):
        return False

    time.sleep(random.uniform(0.5, 1.0))

    btn_after = _find_active_button(page, '[data-e2e="feed-follow"]')
    if btn_after is None:
        return True
    d_after = _follow_icon_d(btn_after)
    return bool(d_after) and d_after != d_before


def _parse_count(text):
    """Parse compact count strings such as '1,234', '12.3K', or '1.2M'."""
    if not text:
        return None
    t = text.strip().upper().replace(",", "")
    mult = 1
    if t.endswith("K"):
        mult, t = 1_000, t[:-1]
    elif t.endswith("M"):
        mult, t = 1_000_000, t[:-1]
    elif t.endswith("B"):
        mult, t = 1_000_000_000, t[:-1]
    try:
        return int(float(t) * mult)
    except ValueError:
        return None


def _active_comment_count(page):
    """Comment count of the active video, or None if unreadable."""
    el = _find_active_button(page, 'strong[data-e2e="comment-count"]')
    if el is None:
        return None
    try:
        return _parse_count(el.inner_text(timeout=500))
    except Exception:
        return None


def _human_type(page, text):
    """Type text char-by-char with human-ish delays."""
    for ch in text:
        page.keyboard.type(ch)
        time.sleep(random.uniform(0.04, 0.18))


def _close_comment_panel(page):
    """Best-effort close of the comment panel so the next video is clean."""
    for sel in ('[data-e2e="comment-close"]', 'button[aria-label*="close" i]'):
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible():
                btn.click(timeout=1500)
                return
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def _focus_comment_box(page):
    """Focus the DraftJS comment editor."""
    box = page.locator('[data-e2e="comment-input"] div[contenteditable="true"]').first
    if box.count() == 0:
        box = page.locator('div[contenteditable="true"]').first
    if box.count() == 0:
        return None

    for sel in ('[data-e2e="comment-text"]', '[data-e2e="comment-input"]'):
        try:
            target = page.locator(sel).first
            if target.count():
                target.click(force=True, timeout=2000)
                break
        except Exception:
            pass
    try:
        box.evaluate("el => el.focus()")
    except Exception:
        pass
    return box


def try_comment(page, mouse_state, comment_text, min_comments=1000):
    """Post one comment on the active video if it has enough comments."""
    count = _active_comment_count(page)
    if count is None or count <= min_comments:
        return False

    btn = _find_active_button(page, '[data-e2e="comment-icon"]')
    if btn is None:
        return False
    if not human_click_locator(page, btn, mouse_state):
        return False
    human_pause(1.5, 3.0)

    box = _focus_comment_box(page)
    if box is None:
        _close_comment_panel(page)
        return False
    human_pause(0.4, 1.0)

    _human_type(page, comment_text)
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
            posted = remaining == "" or remaining != comment_text
        except Exception:
            pass

    _close_comment_panel(page)
    return posted


def fyp_browse(
    page,
    duration_minutes=5,
    like_prob=0.35,
    follows_target=1,
    comments_target=0,
    comments_pool=None,
    comment_prob=0.25,
    comment_min_videos=1000,
    progress_every=5,
    conn=None,
    platform="tiktok",
    account_id=None,
    capture_video_info=True,
    video_capture_config=None,
    ai_comment_config=None,
):
    """Browse the For You feed for approximately ``duration_minutes``."""
    page.goto("https://www.tiktok.com/foryou", timeout=60000)
    human_pause(3, 6)

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    end_time = time.time() + duration_minutes * 60
    video_count = 0
    likes_done = 0
    like_attempts = 0
    like_failure_reasons = {}
    follows_done = 0
    follow_attempts = 0
    comments_done = 0
    comment_attempts = 0
    comments_pool = comments_pool or []
    video_capture_config = video_capture_config or {}
    ai_comment_config = ai_comment_config or {}
    ai_comment_enabled = bool(ai_comment_config.get("enabled"))
    capture_enabled = bool(capture_video_info and conn is not None and account_id)
    capture_session_id = uuid.uuid4().hex
    capture_records = 0
    capture_failures = 0

    while time.time() < end_time:
        video_index = video_count + 1
        stored_video_index = video_index
        current_video_info = {}
        watch_time = random.choices(
            [2, 4, 6, 8, 12, 20],
            weights=[3, 4, 4, 3, 2, 1],
        )[0]

        if capture_enabled:
            try:
                current_video_info = capture_active_video_info(
                    page,
                    max_title_length=int(video_capture_config.get("max_title_length", 300)),
                    max_description_length=int(video_capture_config.get("max_description_length", 600)),
                    capture_timeout_ms=int(video_capture_config.get("capture_timeout_ms", 800)),
                )
            except Exception as exc:
                current_video_info = {
                    "capture_status": "failed",
                    "capture_error": str(exc),
                    "raw_source": "failed",
                }
                capture_failures += 1
            info = dict(current_video_info)
            info.update(
                {
                    "session_id": capture_session_id,
                    "video_index": video_index,
                    "watch_seconds": watch_time,
                }
            )
            recorded_video_index = record_fyp_video_view(conn, platform, account_id, info)
            if recorded_video_index:
                stored_video_index = recorded_video_index
                capture_records += 1
            else:
                capture_failures += 1

        time.sleep(watch_time)

        liked_current = False
        followed_current = False
        commented_current = False

        if random.random() < like_prob:
            like_attempts += 1
            liked, reason = try_like_with_detail(page, mouse_state)
            if liked:
                likes_done += 1
                liked_current = True
                human_pause(0.3, 1.0)
            else:
                like_failure_reasons[reason] = like_failure_reasons.get(reason, 0) + 1

        if follows_done < follows_target and random.random() < 0.05:
            follow_attempts += 1
            if try_follow(page, mouse_state):
                follows_done += 1
                followed_current = True
                human_pause(0.5, 1.5)

        if (
            comments_done < comments_target
            and (comments_pool or ai_comment_enabled)
            and random.random() < comment_prob
        ):
            comment_attempts += 1
            text, source_event = choose_comment_text(
                comments_pool,
                current_video_info,
                ai_comment_config,
                platform,
            )
            log_comment_source_event(conn, platform, account_id, source_event)
            if text and try_comment(page, mouse_state, text, min_comments=comment_min_videos):
                comments_done += 1
                commented_current = True
                human_pause(1.0, 2.5)

        if capture_enabled and (liked_current or followed_current or commented_current):
            if not update_fyp_video_interactions(
                conn,
                platform,
                account_id,
                capture_session_id,
                stored_video_index,
                liked=liked_current if liked_current else None,
                followed=followed_current if followed_current else None,
                commented=commented_current if commented_current else None,
            ):
                capture_failures += 1

        _scroll_to_next_video(page, viewport, mouse_state)
        human_pause(1, 3)
        video_count += 1

        if progress_every and video_count % progress_every == 0:
            print(f"  ... {video_count}v / {likes_done}L / {follows_done}F / {comments_done}C")

    return {
        "videos": video_count,
        "likes": likes_done,
        "like_attempts": like_attempts,
        "like_failures": max(0, like_attempts - likes_done),
        "like_failure_reasons": like_failure_reasons,
        "follows": follows_done,
        "follow_attempts": follow_attempts,
        "follow_failures": max(0, follow_attempts - follows_done),
        "comments": comments_done,
        "comment_attempts": comment_attempts,
        "comment_failures": max(0, comment_attempts - comments_done),
        "video_capture": {
            "enabled": capture_enabled,
            "session_id": capture_session_id,
            "records": capture_records,
            "failures": capture_failures,
        },
    }


def choose_comment_text(comments_pool, video_info, ai_comment_config, platform="tiktok"):
    ai_comment_config = ai_comment_config or {}
    ai_enabled = bool(ai_comment_config.get("enabled"))
    if not ai_enabled:
        if comments_pool:
            return random.choice(comments_pool), None
        return "", None

    context = ai_comment_context(video_info, platform)
    if has_video_context(context):
        result = generate_ai_comment(context, ai_comment_config, read_api_key_from_env)
        if result.get("ok"):
            return result["comment"], {
                "status": "ok",
                "detail": f"comment_source=ai latency_ms={int(result.get('latency_ms') or 0)}",
            }
        reason = result.get("reason") or "failed"
        error = result.get("error") or ""
        if reason == "unsafe_context":
            return "", {
                "status": "fail",
                "detail": comment_source_detail("none", reason, error, fallback="none"),
            }
        if comments_pool:
            return random.choice(comments_pool), {
                "status": "fail",
                "detail": comment_source_detail("pool", reason, error, fallback="pool"),
            }
        return "", {
            "status": "fail",
            "detail": comment_source_detail("none", reason, error, fallback="none"),
        }

    if comments_pool:
        return random.choice(comments_pool), {
            "status": "fail",
            "detail": comment_source_detail("pool", "missing_context", fallback="pool"),
        }
    return "", {
        "status": "fail",
        "detail": comment_source_detail("none", "missing_context", fallback="none"),
    }


def ai_comment_context(video_info, platform):
    video_info = video_info or {}
    return {
        "platform": platform,
        "title": video_info.get("title") or "",
        "description": video_info.get("description") or "",
    }


def comment_source_detail(source, reason, error="", fallback="pool"):
    detail = f"comment_source={source} reason={safe_log_token(reason)} fallback={fallback}"
    if error:
        detail = f"{detail} error={safe_log_message(error)}"
    return detail


def safe_log_token(value):
    return "_".join(str(value or "unknown").strip().split())[:80] or "unknown"


def safe_log_message(value):
    return " ".join(str(value or "").split())[:300]


def log_comment_source_event(conn, platform, account_id, event):
    if not event or conn is None or not account_id:
        return
    log_action(
        conn,
        platform,
        account_id,
        "comment_ai",
        event.get("status") or "fail",
        event.get("detail") or "",
    )
