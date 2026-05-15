"""TikTok actions library (v0.4 — visible-button + state-verified like/follow)."""
import random
import time

from human_mouse import MouseState, human_click_locator


def human_pause(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def _find_active_button(page, selector):
    """Pick the visible button matching `selector` whose vertical centre is
    closest to the viewport centre (i.e. belongs to the active video)."""
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


def _scroll_to_next_video(page, viewport, mouse_state):
    """Advance to the next video. Mostly mouse-wheel, sometimes keyboard."""
    if random.random() < 0.75:
        x = random.randint(int(viewport["width"] * 0.3), int(viewport["width"] * 0.7))
        y = random.randint(int(viewport["height"] * 0.3), int(viewport["height"] * 0.7))
        page.mouse.move(x, y, steps=random.randint(8, 20))
        mouse_state.update(x, y)
        human_pause(0.2, 0.7)
        page.mouse.wheel(0, viewport["height"] + random.randint(50, 250))
    else:
        page.keyboard.press("ArrowDown")


def try_like(page, mouse_state):
    """Like the visible video. Verified via aria-pressed before/after.

    Returns True only if state actually changed false -> true.
    """
    btn = _find_active_button(page, 'button[aria-label*="Like" i]')
    if btn is None:
        return False

    # Skip already-liked videos so we don't accidentally un-like
    try:
        if btn.get_attribute("aria-pressed", timeout=500) == "true":
            return False
    except Exception:
        pass

    if not human_click_locator(page, btn, mouse_state):
        return False

    time.sleep(random.uniform(0.4, 0.9))   # let TikTok update state

    # Re-find the button (could have shifted slightly) and verify
    try:
        btn_after = _find_active_button(page, 'button[aria-label*="Like" i]')
        if btn_after is None:
            return False
        return btn_after.get_attribute("aria-pressed", timeout=500) == "true"
    except Exception:
        return False


def _follow_icon_d(button):
    """Read the SVG path 'd' attribute on a feed-follow button. Empty string on failure."""
    try:
        path = button.locator("svg path").first
        if path.count() == 0:
            return ""
        return path.get_attribute("d", timeout=500) or ""
    except Exception:
        return ""


def try_follow(page, mouse_state):
    """Follow the visible video's creator. Verified via SVG path change.

    The FYP follow button has no aria-label/aria-pressed; the only state signal
    is the icon SVG: '+' (~150 chars) when not following vs checkmark (~250+ chars).
    """
    btn = _find_active_button(page, '[data-e2e="feed-follow"]')
    if btn is None:
        return False

    d_before = _follow_icon_d(btn)
    if not d_before:
        return False
    # Long path = checkmark = already following → skip (avoid un-follow)
    if len(d_before) > 200:
        return False

    if not human_click_locator(page, btn, mouse_state):
        return False

    time.sleep(random.uniform(0.5, 1.0))

    btn_after = _find_active_button(page, '[data-e2e="feed-follow"]')
    if btn_after is None:
        return True  # button gone after follow on some layouts → assume success
    d_after = _follow_icon_d(btn_after)
    return bool(d_after) and d_after != d_before


def fyp_browse(page, duration_minutes=5, like_prob=0.35, follows_target=1, progress_every=5):
    """Browse the For You feed for ~duration_minutes.

    Returns: dict with keys videos, likes, follows.
    """
    page.goto("https://www.tiktok.com/foryou", timeout=60000)
    human_pause(3, 6)

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

    end_time = time.time() + duration_minutes * 60
    video_count = 0
    likes_done = 0
    follows_done = 0

    while time.time() < end_time:
        watch_time = random.choices(
            [2, 4, 6, 8, 12, 20],
            weights=[3, 4, 4, 3, 2, 1],
        )[0]
        time.sleep(watch_time)

        # Maybe like
        if random.random() < like_prob:
            if try_like(page, mouse_state):
                likes_done += 1
                human_pause(0.3, 1.0)

        # Occasionally follow (~5% per video, capped at follows_target)
        if follows_done < follows_target and random.random() < 0.05:
            if try_follow(page, mouse_state):
                follows_done += 1
                human_pause(0.5, 1.5)

        _scroll_to_next_video(page, viewport, mouse_state)
        human_pause(1, 3)
        video_count += 1

        if progress_every and video_count % progress_every == 0:
            print(f"  ... {video_count}v / {likes_done}L / {follows_done}F")

    return {"videos": video_count, "likes": likes_done, "follows": follows_done}
