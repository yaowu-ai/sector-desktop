"""Stats CLI — per-account aggregated counts.

Usage:
    python stats.py              # all time
    python stats.py --today      # today only
    python stats.py --days 7     # last 7 days
"""
import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOG_DB = ROOT / "data" / "actions.db"


def parse_count(detail, key):
    """Extract int after `key=` from a space-separated detail string."""
    if not detail:
        return 0
    for part in detail.split():
        if part.startswith(f"{key}="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return 0
    return 0


def aggregate(since=None):
    """Read action_log and aggregate per account."""
    if not LOG_DB.exists():
        return {}

    conn = sqlite3.connect(LOG_DB)
    if since:
        rows = conn.execute(
            "SELECT account_id, action, status, detail FROM action_log WHERE ts >= ?",
            (since.isoformat(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT account_id, action, status, detail FROM action_log"
        ).fetchall()
    conn.close()

    stats = {}
    for account_id, action, status, detail in rows:
        if account_id not in stats:
            stats[account_id] = {
                "ok": 0, "err": 0, "skip": 0,
                "videos": 0, "likes": 0, "follows": 0, "comments": 0,
            }
        s = stats[account_id]

        if action == "fyp_browse" and status == "ok":
            s["ok"] += 1
            s["videos"] += parse_count(detail, "videos")
        elif action == "session" and status == "error":
            s["err"] += 1
        elif action == "session" and status == "skip":
            s["skip"] += 1
        elif action == "like" and status == "ok":
            s["likes"] += parse_count(detail, "count")
        elif action == "follow" and status == "ok":
            s["follows"] += parse_count(detail, "count")
        elif action == "comment" and status == "ok":
            s["comments"] += parse_count(detail, "count")

    return stats


def print_table(stats, title):
    print()
    print(title)
    print("=" * 80)
    print(f"{'Account':<15} {'OK':>5} {'ERR':>5} {'SKIP':>5} {'Videos':>8} "
          f"{'Likes':>7} {'Follows':>8} {'Cmts':>6}")
    print("-" * 80)

    if not stats:
        print("(no data yet)")
        print("=" * 80)
        return

    totals = {"ok": 0, "err": 0, "skip": 0, "videos": 0,
              "likes": 0, "follows": 0, "comments": 0}
    for acc_id in sorted(stats.keys()):
        s = stats[acc_id]
        print(f"{acc_id:<15} {s['ok']:>5} {s['err']:>5} {s['skip']:>5} "
              f"{s['videos']:>8} {s['likes']:>7} {s['follows']:>8} {s['comments']:>6}")
        for k in totals:
            totals[k] += s[k]

    print("-" * 80)
    print(f"{'Total':<15} {totals['ok']:>5} {totals['err']:>5} {totals['skip']:>5} "
          f"{totals['videos']:>8} {totals['likes']:>7} {totals['follows']:>8} "
          f"{totals['comments']:>6}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="Stats for last N days")
    parser.add_argument("--today", action="store_true",
                        help="Today only (since 00:00 local)")
    args = parser.parse_args()

    since = None
    title = "TikTok Bot Stats - All time"
    if args.today:
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        title = f"TikTok Bot Stats - Today ({since.date()})"
    elif args.days:
        since = datetime.now() - timedelta(days=args.days)
        title = f"TikTok Bot Stats - Last {args.days} days"

    stats = aggregate(since)
    print_table(stats, title)
