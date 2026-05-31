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


def _parse_count(text):
    """'1,234' -> 1234, '12.3K' -> 12300, '1.2M' -> 1200000. None on failure."""
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
    """Focus the DraftJS comment editor; return its contenteditable locator or None.

    The placeholder ('Add comment...') overlays the editor and intercepts pointer
    events, so a plain .click() on the contenteditable fails its actionability
    check. We force-click the input-area container instead, then focus via JS.
    """
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
    """Post one comment on the active video, but only if it has > min_comments
    comments. Returns True only if a comment was actually posted.

    Gating by comment count keeps us on high-traffic videos where one extra
    comment is noise, not a spotlight on a new account.
    """
    count = _active_comment_count(page)
    if count is None or count <= min_comments:
        return False

    # Open the comment panel
    btn = _find_active_button(page, '[data-e2e="comment-icon"]')
    if btn is None:
        return False
    if not human_click_locator(page, btn, mouse_state):
        return False
    human_pause(1.5, 3.0)   # panel slides in + comments load

    # Focus the editable input (DraftJS contenteditable behind a placeholder)
    box = _focus_comment_box(page)
    if box is None:
        _close_comment_panel(page)
        return False
    human_pause(0.4, 1.0)

    _human_type(page, comment_text)
    human_pause(0.6, 1.5)

    # Post: prefer the Post button; only if it's enabled.
    posted = False
    post = page.locator('[data-e2e="comment-post"]').first
    if post.count():
        disabled = (post.get_attribute("aria-disabled") in ("true", "")) or \
                   (post.get_attribute("disabled") is not None)
        if not disabled and human_click_locator(page, post, mouse_state):
            posted = True
    if not posted:
        # Fallback: Ctrl+Enter / Enter submits on some layouts
        try:
            page.keyboard.press("Enter")
            posted = True
        except Exception:
            posted = False

    human_pause(1.0, 2.0)

    # Verify: a successful post clears the input box.
    if posted:
        try:
            remaining = (box.inner_text(timeout=500) or "").strip()
            posted = remaining == "" or remaining != comment_text
        except Exception:
            pass

    _close_comment_panel(page)
    return posted


def fyp_browse(page, duration_minutes=5, like_prob=0.35, follows_target=1,
               comments_target=0, comments_pool=None, comment_prob=0.25,
               comment_min_videos=1000, progress_every=5):
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
    comments_done = 0
    comments_pool = comments_pool or []

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

        # Maybe comment — self-gated to videos with > comment_min_videos comments,
        # capped at comments_target per session.
        if (comments_done < comments_target and comments_pool
                and random.random() < comment_prob):
            text = random.choice(comments_pool)
            if try_comment(page, mouse_state, text, min_comments=comment_min_videos):
                comments_done += 1
                human_pause(1.0, 2.5)

        _scroll_to_next_video(page, viewport, mouse_state)
        human_pause(1, 3)
        video_count += 1

        if progress_every and video_count % progress_every == 0:
            print(f"  ... {video_count}v / {likes_done}L / {follows_done}F / {comments_done}C")

    return {"videos": video_count, "likes": likes_done,
            "follows": follows_done, "comments": comments_done}
