"""Standalone CLI for TikTok sessions."""
import argparse

from core import runtime
from core.runner import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default=None, help="Run only this TikTok account")
    parser.add_argument("--config", default=None, help="Path to accounts.yaml")
    args = parser.parse_args()

    runtime.configure_runtime(args.config)
    runtime.acquire_lock()
    try:
        run(account_id=args.account, platform="tiktok")
    finally:
        runtime.release_lock()
