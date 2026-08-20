"""Standalone CLI for Instagram sessions and long-running warmup schedules."""
from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import datetime, timedelta
from typing import Any, Mapping

from browser_providers import provider_for_account
from core import runtime
from core.runner import run
from platform_config import account_platform

from .bridge import (
    build_instagram_args,
    create_bitbrowser_client,
    load_ins_modules,
    resolve_bitbrowser_profile,
)


def main(argv=None):
    try:
        sys.stdout.reconfigure(
            encoding="utf-8", errors="replace", line_buffering=True, write_through=True
        )
        sys.stderr.reconfigure(
            encoding="utf-8", errors="replace", line_buffering=True, write_through=True
        )
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["AM_DATA_DIR"] = args.data_dir
    runtime.configure_runtime(args.config)

    if args.schedule or args.loop or args.once or args.dry_run:
        return run_long_running(args, parser)

    runtime.acquire_lock()
    try:
        run(account_id=args.account, platform="instagram")
    finally:
        runtime.release_lock()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="platforms.instagram_runner")
    parser.add_argument("--account", default=None, help="Run only this account")
    parser.add_argument("--config", default=None, help="Path to accounts.yaml")
    parser.add_argument("--data-dir", default=None, help="Runtime data directory")
    parser.add_argument("--schedule", action="store_true", help="Run the Instagram daily schedule loop")
    parser.add_argument("--loop", action="store_true", help="Run repeated Instagram warmup rounds")
    parser.add_argument("--once", action="store_true", help="Run one round and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print the schedule or round plan without running")
    return parser


def run_long_running(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    modules = load_ins_modules()
    ensure_original_cli_loaded()
    import ins.cli as ins_cli

    try:
        config, account_args, sessions_range, glob = load_schedule_runtime(args)
    except ValueError as exc:
        parser.error(str(exc))

    if args.once:
        glob.schedule = False
        glob.loop = False
    elif args.schedule:
        glob.schedule = True
        glob.loop = False
    elif args.loop:
        glob.loop = True
        glob.schedule = False

    modules.humanize.LIKE_PROB = float(glob.like_prob)
    modules.humanize.SAVE_PROB = float(glob.save_prob)
    modules.humanize.COMMENT_PROB = float(glob.comment_prob)
    if getattr(glob, "chaos_profiles", ""):
        modules.humanize.CHAOS_PROFILES = set(
            ins_cli._parse_profiles(glob.chaos_profiles)
        )

    gap = ins_cli._parse_gap(glob.gap)
    loop_interval = ins_cli._parse_interval_minutes(glob.loop_interval)
    duration_jitter = ins_cli._parse_float_range(glob.duration_jitter)
    active_windows = modules.schedule.parse_active_hours(glob.active_hours)

    print_runtime_plan(account_args, glob, gap, active_windows)

    if args.dry_run:
        return print_dry_run(modules, ins_cli, account_args, sessions_range, glob)

    conn = modules.storage.init_db()
    aliases = {
        profile: account_id
        for profile, account_id, _ in account_args
        if profile != account_id
    }
    modules.status.StatusStore().merge_aliases(aliases)
    modules.storage.migrate_account_aliases(conn, aliases)
    bitbrowser = create_bitbrowser_client(config)

    runtime.acquire_lock()
    modules.runtime_control.clear_stop_request()
    try:
        if glob.schedule:
            ins_cli._run_schedule(
                account_args,
                sessions_range,
                glob.rest_day_prob,
                glob.min_session_gap_minutes,
                duration_jitter,
                bitbrowser,
                conn,
                glob,
                runtime_loader=lambda: load_schedule_runtime(args, allow_empty=True),
            )
            return 0

        round_num = 0
        while True:
            modules.runtime_control.raise_if_requested()
            round_num += 1
            print(f"\n{'#' * 60}")
            print(f"  INSTAGRAM ROUND {round_num}  -  {datetime.now():%Y-%m-%d %H:%M:%S}")
            print(f"{'#' * 60}")

            all_stats, failed = ins_cli._run_one_round(
                account_args, gap, bitbrowser, conn, glob
            )
            ins_cli._print_round_summary(all_stats, failed)
            ins_cli._notify_round(config, all_stats, failed)

            if not glob.loop:
                break

            wait_min = max(1.0, modules.humanize.lognormal_between(*loop_interval))
            target = datetime.now() + timedelta(minutes=wait_min)
            if not modules.schedule.is_in_active_hours(target, active_windows):
                pushed = modules.schedule.next_window_start(target, active_windows)
                print(
                    f"\n  [loop] next round target {target:%H:%M} is outside active hours, "
                    f"pushed to {pushed:%m-%d %H:%M}"
                )
                target = pushed
            print(f"\n  [loop] sleeping until {target:%m-%d %H:%M} ...")
            modules.humanize.sleep_until(target)
    except (KeyboardInterrupt, modules.runtime_control.StopRequested):
        print("\n[interrupted] Instagram scheduler stopped")
    finally:
        modules.runtime_control.clear_stop_request()
        runtime.release_lock()
        conn.close()
    return 0


def ensure_original_cli_loaded() -> None:
    import ins.cli  # noqa: F401


def load_schedule_runtime(
    cli_args: argparse.Namespace, allow_empty: bool = False
) -> tuple[Mapping[str, Any], list[tuple[str, str, argparse.Namespace]], tuple[int, int], argparse.Namespace]:
    ensure_original_cli_loaded()
    import ins.cli as ins_cli

    config = runtime.load_config()
    accounts = [
        account
        for account in config.get("accounts", [])
        if account.get("enabled", True)
        and account.get("scheduled", True)
        and account_platform(account) == "instagram"
        and (not cli_args.account or str(account.get("id")) == str(cli_args.account))
    ]
    if not accounts and not allow_empty:
        scope = f" account={cli_args.account}" if cli_args.account else ""
        raise ValueError(f"no scheduled Instagram accounts{scope}")

    account_args: list[tuple[str, str, argparse.Namespace]] = []
    for account in accounts:
        provider = provider_for_account(account, config)
        provider.validate_account(account, config)
        if provider.name != "bitbrowser":
            raise ValueError(
                f"account '{account.get('id')}' Instagram scheduler requires BitBrowser"
            )
        profile_id = resolve_bitbrowser_profile(account)
        if not profile_id:
            raise ValueError(
                f"account '{account.get('id')}' requires a BitBrowser profile id"
            )
        account_args.append(
            (
                profile_id,
                str(account.get("id") or profile_id),
                build_instagram_args(account, config),
            )
        )

    glob = build_global_args(account_args, config, cli_args)
    sessions_range = ins_cli._parse_int_range(glob.sessions_per_day)
    if sessions_range[0] < 0 or sessions_range[0] > sessions_range[1]:
        raise ValueError(f"sessions_per_day is invalid: {glob.sessions_per_day}")
    if not (0.0 <= float(glob.rest_day_prob) <= 1.0):
        raise ValueError("rest_day_prob must be between 0 and 1")
    if not (0.0 <= float(glob.round_skip_prob) <= 1.0):
        raise ValueError("round_skip_prob must be between 0 and 1")
    if int(glob.min_session_gap_minutes) < 0:
        raise ValueError("min_session_gap_minutes cannot be negative")
    return config, account_args, sessions_range, glob


def build_global_args(
    account_args: list[tuple[str, str, argparse.Namespace]],
    config: Mapping[str, Any],
    cli_args: argparse.Namespace,
) -> argparse.Namespace:
    if account_args:
        glob = argparse.Namespace(**vars(account_args[0][2]))
    else:
        glob = build_instagram_args({"id": "instagram_schedule_probe"}, config)
    glob.schedule = bool(getattr(cli_args, "schedule", False) or getattr(glob, "schedule", False))
    glob.loop = bool(getattr(cli_args, "loop", False) or getattr(glob, "loop", False))
    glob.once = bool(getattr(cli_args, "once", False))
    glob.dry_run = bool(getattr(cli_args, "dry_run", False))
    return glob


def print_runtime_plan(account_args, glob, gap, active_windows) -> None:
    ids = [account_id for _, account_id, _ in account_args]
    profiles = [profile for profile, _, _ in account_args]
    print(f"Accounts: {ids}")
    print(f"Profiles: {profiles}")
    print(f"Duration per profile: {glob.duration}min")
    print(
        f"Like prob: {glob.like_prob}  Save prob: {glob.save_prob}  "
        f"Comment prob: {glob.comment_prob}"
    )
    print(f"Gap between profiles: {gap[0]}-{gap[1]}s")
    print(f"Active hours: {active_windows}")
    if glob.schedule:
        print(f"Mode: schedule, sessions per day {glob.sessions_per_day}")
    elif glob.loop:
        print(f"Mode: loop, interval {glob.loop_interval}min")
    else:
        print("Mode: once")
    print(f"BitBrowser API: {glob.api_url}\n")


def print_dry_run(modules, ins_cli, account_args, sessions_range, glob) -> int:
    ids = [account_id for _, account_id, _ in account_args]
    if glob.schedule:
        plan = modules.schedule.plan_day(
            ids,
            ins_cli._build_window_map(account_args),
            sessions_range,
            glob.rest_day_prob,
            glob.min_session_gap_minutes,
            datetime.now().date(),
            random.Random(),
            ins_cli._build_one_per_window_map(account_args),
            ins_cli._build_rest_day_prob_map(account_args),
        )
        print(f"[DRY RUN] Instagram schedule for today ({len(plan)} sessions):")
        for when, account_id in plan:
            print(f"  {when:%m-%d %H:%M}  account={account_id}")
        if not plan:
            print("  no sessions planned today")
        return 0

    print("[DRY RUN] Instagram round plan:")
    for profile, account_id, acc_args in account_args:
        print(f"  {account_id} ({profile}): ~{acc_args.duration}min warming")
    return 0
