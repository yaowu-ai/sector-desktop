"""TikTok target-account engagement behavior."""
import random

from core.runtime import (
    get_target_watermark,
    has_followed_target,
    load_comment_file,
    log_action,
    record_target_engagement,
    record_target_follow,
    session_log,
)
from platform_config import ai_comment_config, comments_config, target_engagement_config
from platforms.tiktok.actions import human_pause
from platforms.tiktok.engagement import (
    engage_target_video,
    fetch_recent_videos,
    follow_target_profile,
)
from platforms.tiktok.target_page import navigate_target_page


def run_target_engagement(page, account, config, conn):
    counts = {"videos": 0, "likes": 0, "like_failures": 0, "comments": 0, "follows": 0}
    account_id = account["id"]
    platform = account.get("platform", "tiktok")
    tcfg = target_engagement_config(config, platform)
    if not tcfg.get("enabled") or account_id not in (tcfg.get("participants") or []):
        return counts

    handles = tcfg.get("handles") or []
    first_n = int(tcfg.get("first_run_latest_n", 1))
    max_per_run = int(tcfg.get("max_videos_per_run", 3))
    like_p = float(tcfg.get("like_probability", 0.9))
    comment_p = float(tcfg.get("comment_probability", 0.5))
    ai_comment_cfg = ai_comment_config(config)
    do_follow = bool(tcfg.get("follow", False))
    follow_p = float(tcfg.get("follow_probability", 0.5))
    comment_files = comments_config(config, platform)
    pool = load_comment_file(
        tcfg.get("comments_file") or comment_files.get("target_file", "comments_brand.txt")
    )
    attempted_likes = set()

    for handle in handles:
        try:
            opened, reason = navigate_target_page(page, handle)
            if not opened:
                raise RuntimeError(f"target_profile_open_failed reason={reason}")
        except Exception as exc:
            session_log(f"{account_id} | target {handle} | ERR fetch: {exc}", platform)
            log_action(conn, platform, account_id, "target_fetch", "error", f"{handle}: {exc}")
            continue
        if (
            do_follow
            and not has_followed_target(conn, platform, account_id, handle)
            and random.random() < follow_p
        ):
            follow_errored = False
            try:
                status = follow_target_profile(page, handle)
            except Exception as exc:
                status = "fail"
                follow_errored = True
                log_action(conn, platform, account_id, "target_follow", "error", f"{handle}: {exc}")
            if status in ("followed", "already"):
                record_target_follow(conn, platform, account_id, handle, True)
                if status == "followed":
                    counts["follows"] += 1
                    log_action(conn, platform, account_id, "target_follow", "ok", handle)
                else:
                    log_action(conn, platform, account_id, "target_follow", "skip", f"{handle} reason=already_following")
            elif status == "unknown":
                log_action(conn, platform, account_id, "target_follow", "skip", f"{handle} reason=state_unknown")
            elif not follow_errored:
                log_action(conn, platform, account_id, "target_follow", "fail", handle)

        try:
            recent = fetch_recent_videos(page, handle)
        except Exception as exc:
            log_action(conn, platform, account_id, "target_fetch", "error", f"{handle}: {exc}")
            continue
        log_action(conn, platform, account_id, "target_fetch", "ok", f"{handle}: videos={len(recent)}")
        if not recent:
            log_action(conn, platform, account_id, "target_fetch", "empty", handle)
            continue

        watermark = get_target_watermark(conn, platform, account_id, handle)
        todo = (recent[:first_n] if watermark is None
                else sorted((v for v in recent if int(v) > watermark), key=int))
        todo = todo[:max_per_run]
        if not todo:
            log_action(
                conn,
                platform,
                account_id,
                "target_skip",
                "no_new_videos",
                f"{handle}: watermark={watermark}",
            )
            continue

        for video_id in sorted(todo, key=lambda value: int(value)):
            try:
                result = engage_target_video(
                    page, handle, video_id, pool, like_p, comment_p,
                    ai_comment_config=ai_comment_cfg, conn=conn, platform=platform,
                    account_id=account_id, attempted_likes=attempted_likes,
                )
            except Exception as exc:
                session_log(f"{account_id} | target {handle}/{video_id} | ERR: {exc}", platform)
                log_action(
                    conn,
                    platform,
                    account_id,
                    "target_engage",
                    "error",
                    f"{handle}/{video_id}: {exc}",
                )
                break
            if not result.get("opened", True):
                reason = result.get("open_reason", "unknown")
                session_log(
                    f"{account_id} | target {handle}/{video_id} | OPEN FAIL: {reason}",
                    platform,
                )
                log_action(
                    conn,
                    platform,
                    account_id,
                    "target_engage",
                    "error",
                    f"{handle}/{video_id}: video_open_failed reason={reason}",
                )
                # Stop this handle so a newer success cannot hide this failed video.
                break
            record_target_engagement(
                conn,
                platform,
                account_id,
                handle,
                video_id,
                result["liked"],
                result["commented"],
            )
            log_action(
                conn,
                platform,
                account_id,
                "target_watermark",
                "ok",
                f"{handle}/{video_id}",
            )
            counts["videos"] += 1
            counts["likes"] += int(result["liked"])
            already_liked = result.get("like_reason") == "already_liked"
            if result.get("like_attempted") and not result["liked"] and not already_liked:
                counts["like_failures"] += 1
            counts["comments"] += int(result["commented"])
            like_diagnostics = result.get("like_diagnostics") or {}
            like_detail = (
                f"{handle}/{video_id}"
                + ("" if result["liked"] else f" reason={result.get('like_reason', 'unknown')}")
            )
            if like_diagnostics:
                states = ",".join("liked" if value is True else "unliked" if value is False else "unknown"
                                  for value in like_diagnostics.get("states", []))
                observed = like_diagnostics.get("observed_clicks")
                like_detail += (
                    f" down_requests={like_diagnostics.get('down_requests', 0)}"
                    f" up_requests={like_diagnostics.get('up_requests', 0)}"
                    f" observed_clicks={observed if observed is not None else 'unknown'}"
                    f" states={states or 'none'}"
                )
            if result.get("like_attempted") and not already_liked:
                log_action(
                    conn,
                    platform,
                    account_id,
                    "target_like",
                    "ok" if result["liked"] else "fail",
                    like_detail,
                )
            else:
                log_action(conn, platform, account_id, "target_like", "skip",
                           f"{handle}/{video_id} reason={result.get('like_reason', 'not_attempted')}")
            if result.get("comment_attempted"):
                log_action(
                    conn,
                    platform,
                    account_id,
                    "target_comment",
                    "ok" if result["commented"] else "fail",
                    f"{handle}/{video_id}",
                )
            else:
                log_action(conn, platform, account_id, "target_comment", "skip", f"{handle}/{video_id}")
            log_action(
                conn,
                platform,
                account_id,
                "target_engage",
                "ok",
                f"{handle}/{video_id} like={result['liked']} comment={result['commented']}",
            )
            human_pause(3, 8)

    if counts["videos"] or counts["follows"]:
        session_log(
            f"{account_id} | TARGET | {counts['videos']}v / "
            f"{counts['likes']}L / {counts['like_failures']}LF / "
            f"{counts['comments']}C / {counts['follows']}Fo",
            platform,
        )
    return counts
