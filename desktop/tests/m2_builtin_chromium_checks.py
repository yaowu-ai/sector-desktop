from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import browser_providers as providers  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_data_dir = os.environ.get("AM_DATA_DIR")
    temp_root = ROOT / "desktop" / "tests" / f".m2-temp-{uuid.uuid4().hex}"
    temp_root.mkdir(parents=True)
    try:
        os.environ["AM_DATA_DIR"] = str(temp_root)
        account_a = {"id": "tiktok_A", "browser_provider": "builtin_chromium", "browser": {"provider": "builtin_chromium"}}
        account_b = {"id": "tiktok_B", "browser_provider": "builtin_chromium", "browser": {"provider": "builtin_chromium"}}
        relative_account = {
            "id": "tiktok_relative",
            "browser_provider": "builtin_chromium",
            "browser": {"provider": "builtin_chromium", "user_data_dir": "custom/user-data"},
        }

        dir_a = providers.builtin_user_data_dir(account_a)
        dir_b = providers.builtin_user_data_dir(account_b)
        require(dir_a != dir_b, "two builtin_chromium accounts resolved the same user data dir")
        require(
            dir_a == temp_root / "browser" / "builtin_chromium" / "tiktok_A" / "user-data",
            f"unexpected default user data dir for account A: {dir_a}",
        )
        require(
            dir_b == temp_root / "browser" / "builtin_chromium" / "tiktok_B" / "user-data",
            f"unexpected default user data dir for account B: {dir_b}",
        )
        require(
            providers.builtin_user_data_dir(relative_account) == temp_root / "custom" / "user-data",
            "relative user_data_dir was not resolved under AM_DATA_DIR",
        )

        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        (dir_a / "cache-marker.txt").write_text("account-a", encoding="utf-8")
        (dir_b / "cache-marker.txt").write_text("account-b", encoding="utf-8")
        require((dir_a / "cache-marker.txt").read_text(encoding="utf-8") == "account-a", "account A cache marker changed")
        require((dir_b / "cache-marker.txt").read_text(encoding="utf-8") == "account-b", "account B cache marker changed")

        providers.record_builtin_session(
            account_a,
            pid=12345,
            cdp_endpoint="http://127.0.0.1:45123",
            user_data_dir=dir_a,
            executable="C:/Chromium/chrome.exe",
        )
        runtime_path = providers.builtin_session_path(account_a)
        require(runtime_path.name == "runtime.json", f"runtime record should be runtime.json, got {runtime_path.name}")
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        require(runtime["accountId"] == "tiktok_A", "runtime.json missing accountId")
        require(runtime["provider"] == "builtin_chromium", "runtime.json missing provider")
        require(runtime["lastPid"] == 12345 and runtime["pid"] == 12345, "runtime.json missing PID fields")
        require(runtime["lastPort"] == 45123 and runtime["port"] == 45123, "runtime.json missing port fields")
        require(runtime["lastCdpEndpoint"] == "http://127.0.0.1:45123", "runtime.json missing CDP endpoint")
        require(runtime["userDataDir"] == str(dir_a), "runtime.json missing userDataDir")

        legacy_account = {"id": "legacy", "browser_provider": "builtin_chromium"}
        legacy_path = providers.legacy_builtin_session_path(legacy_account)
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text(json.dumps({"pid": 7, "cdp_endpoint": "http://127.0.0.1:40001"}), encoding="utf-8")
        require(providers.read_builtin_session(legacy_account)["pid"] == 7, "legacy session.json was not readable")

        providers.clear_builtin_session(account_a)
        providers.clear_builtin_session(legacy_account)
        require((dir_b / "cache-marker.txt").exists(), "clearing account A removed account B data")

        status, detail = providers.user_data_dir_access_detail(dir_a)
        require(status == "ok", f"user data dir access check failed: {detail}")
        require("readable=true" in detail and "writable=true" in detail, f"access detail incomplete: {detail}")
        print("m2 builtin chromium checks ok")
        return 0
    finally:
        if original_data_dir is None:
            os.environ.pop("AM_DATA_DIR", None)
        else:
            os.environ["AM_DATA_DIR"] = original_data_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
