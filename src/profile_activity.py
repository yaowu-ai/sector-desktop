"""Read comment-like evidence from the visible TikTok Activity panel."""

import re
import time


COMMENT_LIKE = re.compile(r"^liked\s+your\s+comment\s*(?::|[.·]|$)", re.I)
MAX_ACTIVITY_MATCHES = 10
MAX_ACTIVITY_TEXT_LENGTH = 500


def bounded_activity_text(value, limit=MAX_ACTIVITY_TEXT_LENGTH):
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def comment_like_message(paragraphs):
    """Match an action paragraph, not a phrase quoted inside a comment."""
    for paragraph in paragraphs:
        text = " ".join(paragraph.split())
        if COMMENT_LIKE.match(text):
            return text
    return None


def activity_result(rows, status):
    matches = []
    for row in rows.values():
        action = comment_like_message(row["paragraphs"])
        if action:
            matches.append({
                "text": bounded_activity_text(row["text"]),
                "action": bounded_activity_text(action),
            })
    observed = status in {"loaded_list_stable", "timeout"} and bool(rows)
    return {
        "has_liked_your_comment": True if matches else (False if observed else None),
        "comment_like_notifications_count": len(matches) if observed or matches else None,
        "notifications_scanned": len(rows),
        "matches": matches[:MAX_ACTIVITY_MATCHES],
        "status": status,
        "scope": "loaded_notifications",
        "complete": False,
        "comment_publish_evidence": "observed" if matches else "not_confirmed",
    }


def read_activity(page, timeout=30):
    """Scan loaded rows; a stable scroll is not proof of all notification history.

    TikTok may mark notifications as read when Activity is opened.
    Grouped likes count as one notification, not one person or one comment.
    """
    rows = {}
    status = "timeout"
    deadline = time.monotonic() + timeout
    try:
        page.locator('[data-e2e="nav-activity"]').click(timeout=timeout * 1000)
        panel = page.locator('[data-e2e="inbox-notifications"]:visible')
        panel.wait_for(state="visible", timeout=timeout * 1000)
        panel.get_by_role("tab", name="All activity", exact=True).click(
            timeout=timeout * 1000,
        )
        listing = panel.locator('[data-e2e="inbox-list"]')
        listing.wait_for(state="visible", timeout=timeout * 1000)
        stable = 0
        previous = None
        while time.monotonic() < deadline:
            batch = listing.locator("li").evaluate_all("""elements => elements
                .filter(e => e.getClientRects().length)
                .map(e => ({text: e.innerText.trim(),
                    paragraphs: Array.from(e.querySelectorAll('p')).map(p => p.innerText.trim())}))
            """)
            before = len(rows)
            for row in batch:
                if row["text"]:
                    # Re-rendered rows have no stable notification ID in the observed DOM.
                    key = " ".join(row["text"].split())
                    rows.setdefault(key, row)
            position = listing.evaluate("""e => ({top: e.scrollTop,
                height: e.scrollHeight, viewport: e.clientHeight})""")
            at_bottom = position["top"] + position["viewport"] >= position["height"] - 2
            if rows and len(rows) == before and position == previous and at_bottom:
                stable += 1
            else:
                stable = 0
            if stable >= 3:
                status = "loaded_list_stable"
                break
            previous = position
            listing.evaluate("e => { e.scrollTop = e.scrollHeight; }")
            page.wait_for_timeout(1000)
    except Exception:
        status = "activity_ui_unavailable"
    return activity_result(rows, status)
