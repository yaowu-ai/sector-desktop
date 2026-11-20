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
from platform_config import comments_config, target_engagement_config
from platforms.tiktok.actions import human_pause
from platforms.tiktok.engagement import (
    engage_target_video,
    fetch_recent_videos,
    follow_target_profile,
)


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
    do_follow = bool(tcfg.get("follow", False))
    follow_p = float(tcfg.get("follow_probability", 0.5))
    comment_files = comments_config(config, platform)
    pool = load_comment_file(
        tcfg.get("comments_file") or comment_files.get("target_file", "comments_brand.txt")
    )

    for handle in handles:
        try:
            recent = fetch_recent_videos(page, handle)
        except Exception as exc:
            session_log(f"{account_id} | target {handle} | ERR fetch: {exc}", platform)
            log_action(conn, platform, account_id, "target_fetch", "error", f"{handle}: {exc}")
            continue
        log_action(conn, platform, account_id, "target_fetch", "ok", f"{handle}: videos={len(recent)}")
        if not recent:
            log_action(conn, platform, account_id, "target_fetch", "empty", handle)
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
            elif not follow_errored:
                log_action(conn, platform, account_id, "target_follow", "fail", handle)

        watermark = get_target_watermark(conn, platform, account_id, handle)
        todo = recent[:first_n] if watermark is None else [v for v in recent if int(v) > watermark]
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
                result = engage_target_video(page, handle, video_id, pool, like_p, comment_p)
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
                continue
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
            if result.get("like_attempted") and not result["liked"]:
                counts["like_failures"] += 1
            counts["comments"] += int(result["commented"])
            if result.get("like_attempted"):
                log_action(
                    conn,
                    platform,
                    account_id,
                    "target_like",
                    "ok" if result["liked"] else "fail",
                    (
                        f"{handle}/{video_id}"
                        if result["liked"]
                        else f"{handle}/{video_id} reason={result.get('like_reason', 'unknown')}"
                    ),
                )
            else:
                log_action(conn, platform, account_id, "target_like", "skip", f"{handle}/{video_id}")
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
