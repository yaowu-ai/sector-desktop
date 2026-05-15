"""Diagnostic v2 — finds the like button on the *currently visible* video,
clicks via 3 strategies, and detects state changes via multiple signals
(aria-pressed, class, SVG fill, nearby text).

Usage:
    python test_like.py [--account tiktok_1]

Works whether the BitBrowser profile is already open or not.
"""
import argparse
import sys
import time
from pathlib import Path

import yaml
from patchright.sync_api import sync_playwright

from bitbrowser import BitBrowserClient
from human_mouse import MouseState, human_click_locator

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load(open(ROOT / "config" / "accounts.yaml", encoding="utf-8"))


def find_active_like_button(page):
    """Return the like-button Locator on the currently visible video.

    Picks among all `button[aria-label*="Like"]` matches the one whose
    vertical centre is closest to the viewport centre.
    """
    candidates = page.locator('button[aria-label*="Like" i]')
    n = candidates.count()
    if n == 0:
        return None, None

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    vp_center_y = viewport["height"] / 2

    best_idx = None
    best_dist = float("inf")
    best_box = None
    for i in range(n):
        btn = candidates.nth(i)
        try:
            box = btn.bounding_box(timeout=500)
        except Exception:
            continue
        if not box:
            continue
        # Reject buttons fully outside the viewport.
        if box["y"] + box["height"] < 0 or box["y"] > viewport["height"]:
            continue
        center_y = box["y"] + box["height"] / 2
        dist = abs(center_y - vp_center_y)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
            best_box = box

    if best_idx is None:
        return None, None
    return candidates.nth(best_idx), best_box


def capture_state(button):
    """Read multiple liked-state signals from a button. Returns a dict."""
    s = {}
    try:
        s["aria-pressed"] = button.get_attribute("aria-pressed", timeout=500)
    except Exception:
        s["aria-pressed"] = "<err>"
    try:
        # Liked = first <path> has fill="#FE2C55" (red); unliked = different fill.
        path = button.locator("svg path").first
        if path.count():
            s["svg-fill"] = path.get_attribute("fill", timeout=500)
    except Exception:
        s["svg-fill"] = "<err>"
    try:
        # Like count text (e.g. "21.2K"). Increments on like.
        count_el = button.locator('[data-e2e="like-count"]').first
        if count_el.count():
            s["like-count"] = count_el.inner_text(timeout=500).strip()
    except Exception:
        s["like-count"] = "<err>"
    return s


def diff_states(before, after):
    """Return a human-readable diff. Empty string if identical."""
    keys = set(before) | set(after)
    lines = []
    for k in sorted(keys):
        b, a = before.get(k), after.get(k)
        if b != a:
            lines.append(f"    {k}:")
            lines.append(f"      before: {b!r}")
            lines.append(f"      after:  {a!r}")
    return "\n".join(lines)


def scroll_next(page, viewport):
    page.mouse.move(viewport["width"] // 2, viewport["height"] // 2, steps=10)
    time.sleep(0.3)
    page.mouse.wheel(0, viewport["height"] + 100)
    time.sleep(2.5)


def strategy_a_human_click(page, mouse_state, button):
    return human_click_locator(page, button, mouse_state), "ok"


def strategy_b_native_click(page, mouse_state, button):
    try:
        button.click(timeout=3000)
        return True, "ok"
    except Exception as e:
        return False, f"err: {e}"


def strategy_c_keyboard_l(page, mouse_state, button):
    page.keyboard.press("l")
    return True, "ok"


def run_strategy(page, viewport, mouse_state, label, fn):
    print(f"\n=== Strategy {label} ===")

    btn, box = find_active_like_button(page)
    if btn is None:
        print("  [skip] no active like button found in viewport")
        return
    print(f"  Active button bbox: x={box['x']:.0f} y={box['y']:.0f} {box['width']:.0f}x{box['height']:.0f}")

    before = capture_state(btn)
    print(f"  Before: {before}")

    ok, msg = fn(page, mouse_state, btn)
    print(f"  Click:  returned={ok}  msg={msg}")

    time.sleep(1.5)

    btn_after, _ = find_active_like_button(page)
    if btn_after is None:
        print("  [warn] no like button visible after click (auto-scrolled?)")
        return
    after = capture_state(btn_after)
    print(f"  After:  {after}")

    diff = diff_states(before, after)
    if diff:
        print("  >> STATE CHANGED:")
        print(diff)
    else:
        print("  >> NO STATE CHANGE — click did not register")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="tiktok_1")
    args = parser.parse_args()

    account = next((a for a in CONFIG["accounts"] if a["id"] == args.account), None)
    if not account:
        print(f"Account {args.account} not found")
        sys.exit(1)

    bb = BitBrowserClient(CONFIG["bitbrowser"]["api_url"])
    profile_id = account["bitbrowser_profile_id"]

    was_already_open = bb.is_open(profile_id)
    if was_already_open:
        print(f"[info] Profile {profile_id} is already open — attaching.")
    else:
        print(f"[info] Opening {args.account}...")

    cdp_url = bb.open_browser(profile_id)
    if not was_already_open:
        time.sleep(3)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]

            page = None
            for pg in ctx.pages:
                try:
                    if "tiktok.com" in (pg.url or ""):
                        page = pg
                        break
                except Exception:
                    continue
            if page is None:
                page = ctx.new_page()

            current_url = page.url or ""
            if "/foryou" not in current_url:
                print(f"[info] Navigating to FYP (was on {current_url or 'blank'})...")
                page.goto("https://www.tiktok.com/foryou", timeout=60000)
                time.sleep(5)
            else:
                print(f"[info] Reusing existing FYP tab: {current_url}")
                page.bring_to_front()

            viewport = page.viewport_size or {"width": 1280, "height": 800}
            mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

            for label, fn in [
                ("A: human_click on parent BUTTON", strategy_a_human_click),
                ("B: Playwright native button.click()", strategy_b_native_click),
                ("C: keyboard 'L' shortcut", strategy_c_keyboard_l),
            ]:
                run_strategy(page, viewport, mouse_state, label, fn)
                scroll_next(page, viewport)

            print("\n[info] Done. Browser stays open 30s — go to Profile -> Activity -> Likes")
            time.sleep(30)
            browser.close()
    finally:
        if was_already_open:
            print("[info] Leaving browser open since it was open before this test.")
        else:
            bb.close_browser(profile_id)
            print("[info] Browser closed.")


if __name__ == "__main__":
    main()
