"""Standalone CLI for Instagram sessions."""
from __future__ import annotations

import argparse
import os

from core import runtime
from core.runner import run


def main(argv=None):
    parser = argparse.ArgumentParser(prog="platforms.instagram_runner")
    parser.add_argument("--account", default=None, help="Run only this account")
    parser.add_argument("--config", default=None, help="Path to accounts.yaml")
    parser.add_argument("--data-dir", default=None, help="Runtime data directory")
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["AM_DATA_DIR"] = args.data_dir
    runtime.configure_runtime(args.config)
    runtime.acquire_lock()
    try:
        run(account_id=args.account, platform="instagram")
    finally:
        runtime.release_lock()
    return 0

