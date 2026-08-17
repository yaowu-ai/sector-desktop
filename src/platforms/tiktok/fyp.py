"""TikTok FYP warmup behavior."""
import random

from core.runtime import load_comments, log_action
from platform_config import ai_comment_config, warmup_config
from platforms.tiktok.actions import fyp_browse


def build_fyp_plan(account, config):
    platform = account.get("platform", "tiktok")
    da = warmup_config(config, platform)
    cmt_cfg = da.get("comment", {}) or {}
    video_capture_cfg = normalize_video_capture_config(da.get("video_capture"))
    ai_comment_cfg = ai_comment_config(config)
    comment_enabled = bool(cmt_cfg.get("enabled"))
    comment_range = cmt_cfg.get("comments_per_session", [1, 2])
    comments_pool = load_comments(config, platform) if comment_enabled else []
    ai_comment_enabled = bool(ai_comment_cfg.get("enabled"))
    comments_target = (
        random.randint(*comment_range)
        if comment_enabled and (comments_pool or ai_comment_enabled)
        else 0
    )
    comment_skip_detail = ""
    if not comment_enabled:
        comment_skip_detail = "评论开关关闭（comment.enabled=false）"
    elif not comments_pool and not ai_comment_enabled:
        comment_skip_detail = "评论池为空（comments.txt 无可用评论）"
    elif comments_target <= 0:
        comment_skip_detail = f"本次评论目标数为 0（comments_per_session={comment_range}）"
    return {
        "duration": random.uniform(*da["fyp_browse_minutes"]),
        "like_prob": float(da.get("like_probability", 0.35)),
        "follows_target": random.randint(*da.get("follows_per_session", [0, 1])),
        "comments_pool": comments_pool,
        "comments_target": comments_target,
        "comment_skip_detail": comment_skip_detail,
        "comment_prob": float(cmt_cfg.get("probability", 0.25)),
        "comment_min_videos": int(cmt_cfg.get("min_video_comments", 1000)),
        "video_capture": video_capture_cfg,
        "ai_comment": ai_comment_cfg,
    }


def normalize_video_capture_config(config):
    config = config or {}
    return {
        "enabled": bool(config.get("enabled", True)),
        "max_title_length": int(config.get("max_title_length", 300)),
        "max_description_length": int(config.get("max_description_length", 600)),
        "capture_timeout_ms": int(config.get("capture_timeout_ms", 800)),
    }


def run_tiktok_fyp(page, account, plan, conn):
    account_id = account["id"]
    platform = account.get("platform", "tiktok")
    log_action(
        conn,
        platform,
        account_id,
        "fyp_browse",
        "start",
        f"duration={plan['duration']:.1f}min",
    )
    result = fyp_browse(
        page,
        duration_minutes=plan["duration"],
        like_prob=plan["like_prob"],
        follows_target=plan["follows_target"],
        comments_target=plan["comments_target"],
        comments_pool=plan["comments_pool"],
        comment_prob=plan["comment_prob"],
        comment_min_videos=plan["comment_min_videos"],
        conn=conn,
        platform=platform,
        account_id=account_id,
        capture_video_info=bool((plan.get("video_capture") or {}).get("enabled", True)),
        video_capture_config=plan.get("video_capture") or {},
        ai_comment_config=plan.get("ai_comment") or {},
    )
    videos = result["videos"]
    likes = result["likes"]
    like_failures = result.get("like_failures", 0)
    like_failure_reasons = result.get("like_failure_reasons") or {}
    follows = result["follows"]
    follow_failures = result.get("follow_failures", 0)
    comments = result["comments"]
    comment_failures = result.get("comment_failures", 0)

    log_action(conn, platform, account_id, "fyp_browse", "ok", f"videos={videos}")
    if likes > 0:
        log_action(conn, platform, account_id, "like", "ok", f"count={likes}")
    if like_failure_reasons:
        for reason, count in sorted(like_failure_reasons.items()):
            if count > 0:
                log_action(conn, platform, account_id, "like", "fail", f"reason={reason} count={count}")
    elif like_failures > 0:
        log_action(conn, platform, account_id, "like", "fail", f"count={like_failures}")
    if follows > 0:
        log_action(conn, platform, account_id, "follow", "ok", f"count={follows}")
    if follow_failures > 0:
        log_action(conn, platform, account_id, "follow", "fail", f"count={follow_failures}")
    if plan["comments_target"] <= 0:
        log_action(
            conn,
            platform,
            account_id,
            "comment",
            "skip",
            plan.get("comment_skip_detail") or "评论目标数为 0，未执行评论",
        )
    elif not plan["comments_pool"] and not bool((plan.get("ai_comment") or {}).get("enabled")):
        log_action(conn, platform, account_id, "comment", "skip", "评论池为空（comments.txt 无可用评论）")
    if comments > 0:
        log_action(conn, platform, account_id, "comment", "ok", f"count={comments}")
    if comment_failures > 0:
        log_action(conn, platform, account_id, "comment", "fail", f"count={comment_failures}")

    return {
        "videos": videos,
        "likes": likes,
        "like_failures": like_failures,
        "follows": follows,
        "comments": comments,
    }
