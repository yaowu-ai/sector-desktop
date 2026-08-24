"""Stats CLI — per-account aggregated counts.

Usage:
    python stats.py              # all time
    python stats.py --today      # today only
    python stats.py --days 7     # last 7 days
    python stats.py --target     # brand-target engagement summary (combinable with --today/--days)
"""
import argparse
import json
import sqlite3
from datetime import datetime, timedelta

from runtime_config import resolve_data_dir

LOG_DB = resolve_data_dir() / "actions.db"


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


def parse_value(detail, key):
    """Extract a string after `key=` from a space-separated detail string."""
    if not detail:
        return ""
    for part in detail.split():
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1]
    return ""


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
                "videos": 0, "likes": 0, "like_failures": 0,
                "follows": 0, "comments": 0,
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
        elif action == "like" and status == "fail":
            s["like_failures"] += parse_count(detail, "count")
        elif action == "follow" and status == "ok":
            s["follows"] += parse_count(detail, "count")
        elif action == "comment" and status == "ok":
            s["comments"] += parse_count(detail, "count")

    return stats


def aggregate_target(since=None):
    """Aggregate the target_engagements table → (by_account, by_handle).

    `videos` counts processed videos; `likes`/`comments` sum the recorded flags
    (= client-side success at the time — verify retention on TikTok separately).
    """
    if not LOG_DB.exists():
        return {}, {}

    conn = sqlite3.connect(LOG_DB)
    try:
        if since:
            rows = conn.execute(
                "SELECT our_account, handle, liked, commented "
                "FROM target_engagements WHERE ts >= ?",
                (since.isoformat(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT our_account, handle, liked, commented FROM target_engagements"
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []   # table not created yet (no target runs)

    try:
        if since:
            follow_rows = conn.execute(
                "SELECT our_account, handle FROM target_follows "
                "WHERE followed=1 AND ts >= ?", (since.isoformat(),),
            ).fetchall()
        else:
            follow_rows = conn.execute(
                "SELECT our_account, handle FROM target_follows WHERE followed=1"
            ).fetchall()
    except sqlite3.OperationalError:
        follow_rows = []

    try:
        if since:
            like_failure_rows = conn.execute(
                "SELECT account_id, detail FROM action_log "
                "WHERE action='target_like' AND status='fail' AND ts >= ?",
                (since.isoformat(),),
            ).fetchall()
        else:
            like_failure_rows = conn.execute(
                "SELECT account_id, detail FROM action_log "
                "WHERE action='target_like' AND status='fail'"
            ).fetchall()
    except sqlite3.OperationalError:
        like_failure_rows = []
    conn.close()

    def _acc(acc):
        return by_account.setdefault(
            acc, {"videos": 0, "likes": 0, "like_failures": 0,
                  "comments": 0, "follows": 0, "handles": set()})

    def _hdl(handle):
        return by_handle.setdefault(
            handle, {"videos": 0, "likes": 0, "like_failures": 0,
                     "comments": 0, "follows": 0, "accounts": set()})

    by_account, by_handle = {}, {}
    for acc, handle, liked, commented in rows:
        a = _acc(acc)
        a["videos"] += 1
        a["likes"] += int(liked or 0)
        a["comments"] += int(commented or 0)
        a["handles"].add(handle)

        h = _hdl(handle)
        h["videos"] += 1
        h["likes"] += int(liked or 0)
        h["comments"] += int(commented or 0)
        h["accounts"].add(acc)

    for acc, handle in follow_rows:
        a = _acc(acc)
        a["follows"] += 1
        a["handles"].add(handle)
        h = _hdl(handle)
        h["follows"] += 1
        h["accounts"].add(acc)

    for acc, detail in like_failure_rows:
        handle = parse_value(detail, "handle")
        a = _acc(acc)
        a["like_failures"] += 1
        if handle:
            a["handles"].add(handle)
            h = _hdl(handle)
            h["like_failures"] += 1
            h["accounts"].add(acc)

    return by_account, by_handle


def print_target_table(by_account, by_handle, title):
    print()
    print(title)
    print("=" * 90)

    if not by_account:
        print("(no target engagement yet)")
        print("=" * 90)
        return

    print("By account")
    print(f"{'Account':<15} {'Targets':>8} {'Videos':>8} {'Likes':>7} "
          f"{'LikeFail':>8} {'Comments':>9} {'Follows':>8}")
    print("-" * 90)
    tot = {"videos": 0, "likes": 0, "like_failures": 0,
           "comments": 0, "follows": 0}
    for acc in sorted(by_account):
        s = by_account[acc]
        print(f"{acc:<15} {len(s['handles']):>8} {s['videos']:>8} "
              f"{s['likes']:>7} {s['like_failures']:>8} "
              f"{s['comments']:>9} {s['follows']:>8}")
        for k in tot:
            tot[k] += s[k]
    print("-" * 90)
    print(f"{'Total':<15} {'':>8} {tot['videos']:>8} {tot['likes']:>7} "
          f"{tot['like_failures']:>8} {tot['comments']:>9} {tot['follows']:>8}")

    print()
    print("By target")
    print(f"{'Handle':<20} {'Accounts':>9} {'Videos':>8} {'Likes':>7} "
          f"{'LikeFail':>8} {'Comments':>9} {'Follows':>8}")
    print("-" * 90)
    for handle in sorted(by_handle):
        s = by_handle[handle]
        print(f"{handle:<20} {len(s['accounts']):>9} {s['videos']:>8} "
              f"{s['likes']:>7} {s['like_failures']:>8} "
              f"{s['comments']:>9} {s['follows']:>8}")
    print("=" * 90)


def print_table(stats, title):
    print()
    print(title)
    print("=" * 92)
    print(f"{'Account':<15} {'OK':>5} {'ERR':>5} {'SKIP':>5} {'Videos':>8} "
          f"{'Likes':>7} {'LikeFail':>8} {'Follows':>8} {'Cmts':>6}")
    print("-" * 92)

    if not stats:
        print("(no data yet)")
        print("=" * 92)
        return

    totals = {"ok": 0, "err": 0, "skip": 0, "videos": 0,
              "likes": 0, "like_failures": 0,
              "follows": 0, "comments": 0}
    for acc_id in sorted(stats.keys()):
        s = stats[acc_id]
        print(f"{acc_id:<15} {s['ok']:>5} {s['err']:>5} {s['skip']:>5} "
              f"{s['videos']:>8} {s['likes']:>7} {s['like_failures']:>8} "
              f"{s['follows']:>8} {s['comments']:>6}")
        for k in totals:
            totals[k] += s[k]

    print("-" * 92)
    print(f"{'Total':<15} {totals['ok']:>5} {totals['err']:>5} {totals['skip']:>5} "
          f"{totals['videos']:>8} {totals['likes']:>7} "
          f"{totals['like_failures']:>8} {totals['follows']:>8} "
          f"{totals['comments']:>6}")
    print("=" * 92)


def target_summary_json(by_account, by_handle, scope, since):
    return {
        "scope": scope,
        "since": since.isoformat() if since else None,
        "by_account": [
            {
                "account_id": account_id,
                "videos": stats["videos"],
                "likes": stats["likes"],
                "like_failures": stats["like_failures"],
                "comments": stats["comments"],
                "follows": stats["follows"],
                "handles": sorted(stats["handles"]),
            }
            for account_id, stats in sorted(by_account.items())
        ],
        "by_handle": [
            {
                "handle": handle,
                "videos": stats["videos"],
                "likes": stats["likes"],
                "like_failures": stats["like_failures"],
                "comments": stats["comments"],
                "follows": stats["follows"],
                "accounts": sorted(stats["accounts"]),
            }
            for handle, stats in sorted(by_handle.items())
        ],
    }


def fyp_summary_json(stats, scope, since):
    totals = {"ok": 0, "err": 0, "skip": 0, "videos": 0,
              "likes": 0, "like_failures": 0,
              "follows": 0, "comments": 0}
    by_account = []
    for account_id, values in sorted(stats.items()):
        row = {"account_id": account_id, **values}
        by_account.append(row)
        for key in totals:
            totals[key] += values[key]
    return {
        "scope": scope,
        "since": since.isoformat() if since else None,
        "by_account": by_account,
        "total": totals,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="Stats for last N days")
    parser.add_argument("--today", action="store_true",
                        help="Today only (since 00:00 local)")
    parser.add_argument("--target", action="store_true",
                        help="Brand-target engagement summary instead of FYP stats")
    parser.add_argument("--json", action="store_true",
                        help="Print machine-readable JSON instead of tables")
    args = parser.parse_args()

    since = None
    scope = "All time"
    if args.today:
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        scope = f"Today ({since.date()})"
    elif args.days:
        since = datetime.now() - timedelta(days=args.days)
        scope = f"Last {args.days} days"

    if args.target:
        by_account, by_handle = aggregate_target(since)
        if args.json:
            print(json.dumps(
                target_summary_json(by_account, by_handle, scope, since),
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print_target_table(by_account, by_handle, f"Target Engagement - {scope}")
    else:
        stats = aggregate(since)
        if args.json:
            print(json.dumps(
                fyp_summary_json(stats, scope, since),
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print_table(stats, f"TikTok Bot Stats - {scope}")
