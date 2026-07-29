"""Compatibility CLI entrypoint for the platform-aware account runner."""
import argparse

from core import runtime
from core.runner import find_account, run

configure_runtime = runtime.configure_runtime
pid_alive = runtime.pid_alive
acquire_lock = runtime.acquire_lock
release_lock = runtime.release_lock
init_db = runtime.init_db
log_action = runtime.log_action
session_log = runtime.session_log


def is_tiktok_account(account):
    return str(account.get("platform", "tiktok")).strip().lower() == "tiktok"


def auto_close_profile_enabled():
    return runtime.auto_close_profile_enabled()


def __getattr__(name):
    if name in {
        "CONFIG_PATH",
        "DATA_DIR",
        "COMMENTS_PATH",
        "LOG_DB",
        "SESSION_LOG",
        "LOCK_FILE",
        "STOP_AFTER_CURRENT_FILE",
    }:
        return getattr(runtime, name)
    raise AttributeError(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default=None, help="Run only this account; default: all enabled")
    parser.add_argument("--platform", default=None, help="Run accounts for this platform; default: all platforms")
    parser.add_argument("--config", default=None, help="Path to accounts.yaml; default: config/accounts.yaml")
    parser.add_argument("--data-dir", default=None, help="Runtime data directory; default: data next to config")
    args = parser.parse_args()

    if args.data_dir:
        import os
        os.environ["AM_DATA_DIR"] = args.data_dir
    configure_runtime(args.config)
    acquire_lock()
    try:
        run(account_id=args.account, platform=args.platform)
    finally:
        release_lock()
