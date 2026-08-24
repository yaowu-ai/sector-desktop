"""Installable runtime CLI for 星域.

This entrypoint is intentionally thin: account execution still goes through the
existing core runner so current BitBrowser behavior remains unchanged.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

RUNTIME_VERSION = "0.1.0"
SCHEMA_VERSION = 1
SUPPORTED_COMMANDS = ["run", "scheduler", "gmail", "diagnostic", "ai-comment", "version"]


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser():
    parser = argparse.ArgumentParser(prog="account-matrix-runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run account tasks")
    add_config_and_data_args(run_parser)
    run_parser.add_argument("--account", default=None, help="Run only this account")
    run_parser.add_argument("--platform", default=None, help="Run accounts for this platform")
    run_parser.set_defaults(func=cmd_run)

    scheduler_parser = subparsers.add_parser("scheduler", help="Start the scheduler service")
    add_config_and_data_args(scheduler_parser)
    scheduler_parser.add_argument("--host", default="127.0.0.1", help="Scheduler host")
    scheduler_parser.add_argument("--port", type=int, default=9601, help="Scheduler port")
    scheduler_parser.set_defaults(func=cmd_scheduler)

    gmail_parser = subparsers.add_parser("gmail", help="Run Gmail setup flow")
    gmail_parser.add_argument("gmail_args", nargs=argparse.REMAINDER)
    gmail_parser.set_defaults(func=cmd_gmail)

    diagnostic_parser = subparsers.add_parser("diagnostic", help="Inspect runtime health")
    add_config_and_data_args(diagnostic_parser)
    diagnostic_parser.add_argument("--kind", choices=["like", "comment"], default=None)
    diagnostic_parser.add_argument("--account", default=None)
    diagnostic_parser.add_argument("--min", type=int, default=None)
    diagnostic_parser.add_argument("--max-scroll", type=int, default=None)
    diagnostic_parser.add_argument("--no-post", action="store_true")
    diagnostic_parser.add_argument("--json", action="store_true", help="Print JSON")
    diagnostic_parser.set_defaults(func=cmd_diagnostic)

    ai_comment_parser = subparsers.add_parser("ai-comment", help="Generate or test an AI comment")
    ai_comment_parser.set_defaults(func=cmd_ai_comment)

    version_parser = subparsers.add_parser("version", help="Print runtime version")
    version_parser.add_argument("--json", action="store_true", help="Print JSON")
    version_parser.set_defaults(func=cmd_version)

    return parser


def add_config_and_data_args(parser):
    parser.add_argument("--config", default=None, help="Path to accounts.yaml")
    parser.add_argument("--data-dir", default=None, help="Runtime data directory")


def cmd_run(args):
    apply_runtime_env(args)
    from core import runtime
    from core.runner import run

    runtime.configure_runtime(args.config)
    runtime.acquire_lock()
    try:
        run(account_id=args.account, platform=args.platform)
    finally:
        runtime.release_lock()
    return 0


def cmd_scheduler(args):
    apply_runtime_env(args)
    import uvicorn
    import scheduler as scheduler_module

    scheduler_module.configure_runtime(args.config)
    uvicorn.run(
        scheduler_module.app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0

def cmd_gmail(args):
    import gmail_setup

    previous_argv = sys.argv
    sys.argv = ["gmail_setup.py", *args.gmail_args]
    try:
        return gmail_setup.main()
    finally:
        sys.argv = previous_argv


def cmd_diagnostic(args):
    apply_runtime_env(args)
    if args.kind:
        return run_interactive_diagnostic(args)
    payload = build_diagnostic_payload(args.config)
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(f"runtime: {payload['status']}")
        for check in payload["checks"]:
            print(f"{check['name']}: {check['status']} - {check['detail']}")
    return 0 if payload["status"] in {"ok", "warning"} else 1


def cmd_ai_comment(_args):
    from ai_comment import generate_ai_comment, read_api_key_from_env

    payload = json.loads(sys.stdin.read() or "{}")
    config = payload.get("config") or {}
    result = generate_ai_comment(payload.get("context") or {}, config, read_api_key_from_env)
    result["provider"] = str(config.get("provider") or "")
    result["model"] = str(config.get("model") or "")
    print_json(result)
    return 0


def print_json(payload):
    print(json.dumps(payload, ensure_ascii=True))


def run_interactive_diagnostic(args):
    if not args.account:
        raise SystemExit("--account is required when --kind is provided")

    if args.kind == "like":
        module_name = "test_like"
        script_argv = ["test_like.py", "--account", args.account]
    else:
        module_name = "test_comment"
        script_argv = ["test_comment.py", "--account", args.account]
        if args.min is not None:
            script_argv.extend(["--min", str(args.min)])
        if args.max_scroll is not None:
            script_argv.extend(["--max-scroll", str(args.max_scroll)])
        if args.no_post:
            script_argv.append("--no-post")

    if args.config:
        script_argv.extend(["--config", args.config])

    module = __import__(module_name)
    previous_argv = sys.argv
    sys.argv = script_argv
    try:
        return module.main()
    finally:
        sys.argv = previous_argv


def cmd_version(args):
    payload = version_payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(payload["runtimeVersion"])
    return 0


def apply_runtime_env(args):
    if getattr(args, "data_dir", None):
        os.environ["AM_DATA_DIR"] = args.data_dir
    if getattr(args, "config", None):
        os.environ["AM_CONFIG_PATH"] = args.config


def build_diagnostic_payload(config_path=None):
    from runtime_config import resolve_comments_path, resolve_config_path, resolve_data_dir
    from platform_config import load_runtime_config
    from browser_providers import diagnose_account_browser, provider_capability_matrix

    config = resolve_config_path(config_path)
    data_dir = resolve_data_dir(config)
    comments = resolve_comments_path("comments.txt", config)
    brand_comments = resolve_comments_path("comments_brand.txt", config)
    checks = []

    def add_check(name, ok, detail, warning=False):
        checks.append(
            {
                "name": name,
                "status": "ok" if ok else ("warning" if warning else "error"),
                "detail": detail,
            }
        )

    add_check("config", config.is_file(), str(config))
    add_check("dataDir", data_dir.exists() and data_dir.is_dir(), str(data_dir), warning=True)
    add_check("comments", comments.is_file(), str(comments), warning=True)
    add_check("brandComments", brand_comments.is_file(), str(brand_comments), warning=True)
    patchright_driver = check_patchright_driver()
    add_check(
        "patchrightDriver",
        patchright_driver["status"] == "ok",
        patchright_driver["detail"],
    )
    patchright_check = check_patchright_startup()
    add_check(
        "patchrightStartup",
        patchright_check["status"] == "ok",
        patchright_check["detail"],
    )

    account_count = 0
    enabled_accounts = 0
    if config.is_file():
        try:
            raw = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
            runtime_config = load_runtime_config(raw)
            accounts = runtime_config.get("accounts", [])
            account_count = len(accounts)
            enabled_accounts = sum(1 for account in accounts if account.get("enabled", True))
            add_check("configSchema", True, f"{account_count} account(s)")
            for account in accounts:
                if not account.get("enabled", True):
                    continue
                diagnosis = diagnose_account_browser(account, runtime_config)
                add_check(
                    f"browser:{account.get('id', '<unknown>')}",
                    diagnosis["status"] == "ok",
                    diagnosis["provider"],
                    warning=diagnosis["status"] != "ok",
                )
        except Exception as exc:
            add_check("configSchema", False, str(exc))

    status = "ok"
    if any(check["status"] == "error" for check in checks):
        status = "error"
    elif any(check["status"] == "warning" for check in checks):
        status = "warning"

    return {
        "status": status,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "version": version_payload(),
        "paths": {
            "configPath": str(config),
            "dataDir": str(data_dir),
            "commentsPath": str(comments),
            "brandCommentsPath": str(brand_comments),
            "actionsDbPath": str(data_dir / "actions.db"),
            "sessionsLogPath": str(data_dir / "sessions.log"),
        },
        "accounts": {
            "total": account_count,
            "enabled": enabled_accounts,
        },
        "browserProviders": provider_capability_matrix(),
        "checks": checks,
    }


def check_patchright_startup():
    try:
        from patchright_runtime import patchright_startup_check

        return patchright_startup_check()
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def check_patchright_driver():
    try:
        from patchright_runtime import patchright_driver_check

        return patchright_driver_check()
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def version_payload():
    return {
        "runtimeVersion": RUNTIME_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "supportedCommands": SUPPORTED_COMMANDS,
    }


if __name__ == "__main__":
    raise SystemExit(main())
