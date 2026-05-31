"""Diagnostic for the comment action.

Walks the FYP looking for a video whose comment count exceeds --min, opens the
comment panel, DUMPS the relevant HTML (count element, comment icon, input box,
post button) so selectors can be confirmed, then optionally types + posts a test
comment and checks whether it registered.

Usage:
    python test_comment.py [--account tiktok_1] [--min 1000] [--no-post]

--no-post    only locate + dump HTML, never actually submit a comment.
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
from actions import (
    _find_active_button,
    _active_comment_count,
    _human_type,
    _close_comment_panel,
    _focus_comment_box,
)

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load(open(ROOT / "config" / "accounts.yaml", encoding="utf-8"))

TEST_COMMENT = "Love this! 🔥"


def outer_html(locator, label):
    try:
        if locator is None or locator.count() == 0:
            print(f"  [{label}] NOT FOUND")
            return
        html = locator.first.evaluate("el => el.outerHTML", timeout=1000)
        snippet = html if len(html) < 600 else html[:600] + " …(truncated)"
        print(f"  [{label}] {snippet}")
    except Exception as e:
        print(f"  [{label}] err: {e}")


def scroll_next(page, viewport):
    page.mouse.move(viewport["width"] // 2, viewport["height"] // 2, steps=10)
    time.sleep(0.3)
    page.mouse.wheel(0, viewport["height"] + 100)
    time.sleep(2.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="tiktok_1")
    parser.add_argument("--min", type=int, default=1000,
                        help="Find a video with more than this many comments")
    parser.add_argument("--no-post", action="store_true",
                        help="Locate + dump HTML only; do not submit a comment")
    parser.add_argument("--max-scroll", type=int, default=20,
                        help="Give up after scanning this many videos")
    args = parser.parse_args()

    account = next((a for a in CONFIG["accounts"] if a["id"] == args.account), None)
    if not account:
        print(f"Account {args.account} not found")
        sys.exit(1)

    bb = BitBrowserClient(CONFIG["bitbrowser"]["api_url"])
    profile_id = account["bitbrowser_profile_id"]

    was_already_open = bb.is_open(profile_id)
    print(f"[info] Profile {'already open — attaching' if was_already_open else 'opening'}.")
    cdp_url = bb.open_browser(profile_id)
    if not was_already_open:
        time.sleep(3)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]

            page = None
            for pg in ctx.pages:
                if "tiktok.com" in (pg.url or ""):
                    page = pg
                    break
            if page is None:
                page = ctx.new_page()

            if "/foryou" not in (page.url or ""):
                print("[info] Navigating to FYP...")
                page.goto("https://www.tiktok.com/foryou", timeout=60000)
                time.sleep(5)
            else:
                page.bring_to_front()

            viewport = page.viewport_size or {"width": 1280, "height": 800}
            mouse_state = MouseState(viewport["width"] // 2, viewport["height"] // 2)

            # 1) Find a qualifying video.
            print(f"\n[info] Scanning for a video with > {args.min} comments...")
            qualified = False
            for i in range(args.max_scroll):
                count = _active_comment_count(page)
                print(f"  video {i+1}: comment_count = {count}")
                if count is not None and count > args.min:
                    qualified = True
                    break
                scroll_next(page, viewport)

            if not qualified:
                print(f"\n[FAIL] No video with > {args.min} comments in {args.max_scroll} "
                      f"scrolls. Re-run with a lower --min to test the flow.")
                print("[hint] If counts read as None, the count selector is wrong — "
                      "send me the HTML around the comment number on the right rail.")
                _dump_rail(page)
                return

            # 2) Dump the right-rail HTML for this video.
            print("\n=== Right-rail HTML (active video) ===")
            _dump_rail(page)

            # 3) Open the comment panel.
            print("\n[info] Opening comment panel...")
            icon = _find_active_button(page, '[data-e2e="comment-icon"]')
            if icon is None:
                print("  [FAIL] comment-icon not found — send me the comment button HTML.")
                return
            human_click_locator(page, icon, mouse_state)
            time.sleep(2.5)

            # 4) Dump the panel input + post button.
            print("\n=== Comment panel HTML ===")
            outer_html(page.locator('[data-e2e="comment-input"]'), "comment-input wrapper")
            outer_html(page.locator('[data-e2e="comment-input"] div[contenteditable="true"]'),
                       "contenteditable (preferred)")
            outer_html(page.locator('div[contenteditable="true"]'), "any contenteditable")
            outer_html(page.locator('[data-e2e="comment-post"]'), "comment-post button")

            if args.no_post:
                print("\n[info] --no-post set; not submitting. Closing panel.")
                _close_comment_panel(page)
                time.sleep(2)
                return

            # 5) Type + post a test comment.
            box = _focus_comment_box(page)
            if box is None:
                print("  [FAIL] no input box found — send me the panel HTML above.")
                return

            time.sleep(0.5)
            print(f"\n[info] Typing test comment: {TEST_COMMENT!r}")
            _human_type(page, TEST_COMMENT)
            time.sleep(1.0)

            typed = (box.inner_text(timeout=500) or "").strip()
            print(f"  input box now contains: {typed!r}")

            post = page.locator('[data-e2e="comment-post"]').first
            if post.count():
                disabled = (post.get_attribute("aria-disabled") in ("true", "")) or \
                           (post.get_attribute("disabled") is not None)
                print(f"  post button disabled? {disabled}")
                if not disabled:
                    human_click_locator(page, post, mouse_state)
                    print("  clicked post button")
                else:
                    page.keyboard.press("Enter")
                    print("  post disabled — pressed Enter as fallback")
            else:
                page.keyboard.press("Enter")
                print("  no post button — pressed Enter")

            time.sleep(2.0)
            remaining = (box.inner_text(timeout=500) or "").strip()
            print(f"  input box after post: {remaining!r}")
            if remaining == "" or remaining != TEST_COMMENT:
                print("  >> LIKELY POSTED (input cleared). Verify in the panel / your profile.")
            else:
                print("  >> NOT POSTED (input unchanged) — send me the post-button HTML.")

            print("\n[info] Browser stays open 30s so you can eyeball the comment.")
            time.sleep(30)
    finally:
        if was_already_open:
            print("[info] Leaving browser open (was open before test).")
        else:
            bb.close_browser(profile_id)
            print("[info] Browser closed.")


def _dump_rail(page):
    outer_html(page.locator('strong[data-e2e="comment-count"]'), "comment-count")
    outer_html(page.locator('[data-e2e="comment-icon"]'), "comment-icon")


if __name__ == "__main__":
    main()
