"""Unified platform-aware account runner."""
import random
import time

from notify import send as notify_send
from platform_config import account_platform, normalize_platform
from core import runtime
from platforms.registry import get_runner

ACCOUNT_GAP_SECONDS = (30, 120)


def find_account(config, account_id):
    for account in config["accounts"]:
        if account["id"] == account_id:
            return account
    raise ValueError(f"Account {account_id} not in config")


def run(account_id=None, platform=None):
    """Run one account, or all enabled accounts through platform runners."""
    config = runtime.load_config()

    if account_id:
        account = find_account(config, account_id)
        requested_platform = normalize_platform(platform or account_platform(account))
        actual_platform = account_platform(account)
        if actual_platform != requested_platform:
            raise ValueError(
                f"account {account_id} belongs to platform={actual_platform}, "
                f"not request platform={requested_platform}"
            )
        accounts = [account]
    else:
        requested_platform = normalize_platform(platform) if platform else None
        accounts = [
            account
            for account in config["accounts"]
            if account.get("enabled", True)
            and (requested_platform is None or account_platform(account) == requested_platform)
        ]

    executable_accounts = [
        account for account in accounts if get_runner(account_platform(account)).can_execute()
    ]
    reserved_accounts = [
        account for account in accounts if not get_runner(account_platform(account)).can_execute()
    ]

    for account in reserved_accounts:
        print(get_runner(account_platform(account)).skip_message(account))

    if not executable_accounts:
        scope = f" {requested_platform}" if requested_platform else ""
        print(f"[info] no executable{scope} accounts to run")
        return []

    runtime.session_log(f"BATCH START | {len(executable_accounts)} account(s)")
    conn = runtime.init_db()
    summaries = []
    try:
        for index, account in enumerate(executable_accounts):
            runner = get_runner(account_platform(account))
            summary = runner.run_session(account, config, conn)
            summaries.append(summary)
            if index < len(executable_accounts) - 1:
                if runtime.STOP_AFTER_CURRENT_FILE.exists():
                    runtime.session_log("BATCH STOP | stop_after_current.flag detected")
                    runtime.STOP_AFTER_CURRENT_FILE.unlink(missing_ok=True)
                    break
                gap = random.uniform(*ACCOUNT_GAP_SECONDS)
                print(f"[gap] sleeping {gap:.0f}s before next account")
                time.sleep(gap)
    finally:
        conn.close()

    title, body = build_batch_message(summaries)
    runtime.session_log(f"BATCH END | {title}")
    notify_send(config.get("notify", {}), title, body)
    return summaries


def build_batch_message(summaries):
    ok = sum(1 for item in summaries if item["status"] == "ok")
    err = sum(1 for item in summaries if item["status"] == "error")
    skip = sum(1 for item in summaries if item["status"] == "skip")
    total_videos = sum(item["videos"] for item in summaries)
    total = len(summaries)
    registration_task = bool(summaries) and all(
        item.get("task_type") == "tiktok_register" for item in summaries
    )

    if registration_task:
        title = f"星域 注册: {ok}/{total} 完成"
        incomplete = err + skip
        if incomplete:
            title = f"[ERR] 星域 注册: {ok}/{total} 完成, {incomplete} 失败"

        lines = [
            f"OK={ok}  ERR={err}  SKIP={skip}",
            "",
            "Per-account:",
        ]
        for item in summaries:
            platform = item.get("platform", "tiktok")
            prefix = f"  - {item['account_id']} ({platform})"
            username = item.get("registered_username")
            username_detail = f", username={username}" if username else ""
            if item["status"] == "ok":
                lines.append(
                    f"{prefix}: REGISTERED ({item['duration_actual_min']}min{username_detail})"
                )
            elif item["status"] == "error":
                lines.append(f"{prefix}: ERROR - {item['error']}")
            else:
                lines.append(f"{prefix}: {item['status'].upper()} - {item.get('error') or ''}")
        return title, "\n".join(lines)

    title = f"星域 bot: {ok}/{total} OK"
    if err:
        title = f"[ERR] 星域 bot: {ok}/{total} OK, {err} failed"

    lines = [
        f"OK={ok}  ERR={err}  SKIP={skip}  videos={total_videos}",
        "",
        "Per-account:",
    ]
    for item in summaries:
        platform = item.get("platform", "tiktok")
        prefix = f"  - {item['account_id']} ({platform})"
        if item["status"] == "ok":
            target = ""
            if item.get("target_videos") or item.get("target_follows"):
                target = (
                    f", target {item['target_videos']}v/"
                    f"{item.get('target_likes', 0)}L/{item.get('target_comments', 0)}C/"
                    f"{item.get('target_follows', 0)}Fo"
                )
            lines.append(
                f"{prefix}: OK ({item['videos']}v / {item['likes']}L / "
                f"{item.get('like_failures', 0)}LF / {item['follows']}F / "
                f"{item.get('comments', 0)}C{target}, "
                f"{item['duration_actual_min']}min)"
            )
        elif item["status"] == "error":
            lines.append(f"{prefix}: ERROR - {item['error']}")
        else:
            lines.append(f"{prefix}: {item['status'].upper()}")
    return title, "\n".join(lines)
