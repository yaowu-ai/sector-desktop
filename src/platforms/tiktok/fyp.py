"""TikTok FYP warmup behavior."""
import random

from core.runtime import load_comments, log_action
from platform_config import warmup_config
from platforms.tiktok.actions import fyp_browse


def build_fyp_plan(account, config):
    platform = account.get("platform", "tiktok")
    da = warmup_config(config, platform)
    cmt_cfg = da.get("comment", {}) or {}
    comments_pool = load_comments(config, platform) if cmt_cfg.get("enabled") else []
    comments_target = (
        random.randint(*cmt_cfg.get("comments_per_session", [1, 2]))
        if comments_pool else 0
    )
    return {
        "duration": random.uniform(*da["fyp_browse_minutes"]),
        "like_prob": float(da.get("like_probability", 0.35)),
        "follows_target": random.randint(*da.get("follows_per_session", [0, 1])),
        "comments_pool": comments_pool,
        "comments_target": comments_target,
        "comment_prob": float(cmt_cfg.get("probability", 0.25)),
        "comment_min_videos": int(cmt_cfg.get("min_video_comments", 1000)),
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
    )
    videos = result["videos"]
    likes = result["likes"]
    like_failures = result.get("like_failures", 0)
    follows = result["follows"]
    follow_failures = result.get("follow_failures", 0)
    comments = result["comments"]
    comment_failures = result.get("comment_failures", 0)

    log_action(conn, platform, account_id, "fyp_browse", "ok", f"videos={videos}")
    if likes > 0:
        log_action(conn, platform, account_id, "like", "ok", f"count={likes}")
    if like_failures > 0:
        log_action(conn, platform, account_id, "like", "fail", f"count={like_failures}")
    if follows > 0:
        log_action(conn, platform, account_id, "follow", "ok", f"count={follows}")
    if follow_failures > 0:
        log_action(conn, platform, account_id, "follow", "fail", f"count={follow_failures}")
    if plan["comments_target"] <= 0:
        log_action(conn, platform, account_id, "comment", "skip", "disabled")
    elif not plan["comments_pool"]:
        log_action(conn, platform, account_id, "comment", "skip", "comment pool empty")
    if comments > 0:
        log_action(conn, platform, account_id, "comment", "ok", f"count={comments}")
    if comment_failures > 0:
        log_action(conn, platform, account_id, "comment", "fail", f"count={comment_failures}")

    return {
        "videos": videos,
        "likes": likes,
        "follows": follows,
        "comments": comments,
    }
