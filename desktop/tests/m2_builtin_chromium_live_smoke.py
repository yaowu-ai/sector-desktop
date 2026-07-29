from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import browser_providers as providers  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_data_dir = os.environ.get("AM_DATA_DIR")
    data_dir = ROOT / "desktop" / "tests" / ".m2-live-data"
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["AM_DATA_DIR"] = str(data_dir)

    config = {"browser": {"default_provider": "bitbrowser"}}
    provider = providers.BuiltinChromiumProvider()
    accounts = [
        {"id": "m2_live_a", "browser_provider": "builtin_chromium", "browser": {"provider": "builtin_chromium"}},
        {"id": "m2_live_b", "browser_provider": "builtin_chromium", "browser": {"provider": "builtin_chromium"}},
    ]
    sessions = []
    try:
        for account in accounts:
            session = provider.start_session(account, config)
            sessions.append(session)

        require(sessions[0].cdp_endpoint != sessions[1].cdp_endpoint, "CDP endpoints should be different")
        require(sessions[0].user_data_dir != sessions[1].user_data_dir, "user data dirs should be different")
        for session in sessions:
            runtime_path = providers.builtin_session_path(session.account_id)
            require(runtime_path.is_file(), f"missing runtime record: {runtime_path}")
            payload = json.loads(runtime_path.read_text(encoding="utf-8"))
            require(payload["accountId"] == session.account_id, "runtime accountId mismatch")
            require(payload["lastPid"] == session.process_id, "runtime PID mismatch")
            require(payload["lastPort"], "runtime port missing")
            require(payload["lastCdpEndpoint"] == session.cdp_endpoint, "runtime CDP endpoint mismatch")
            require(Path(session.user_data_dir).is_dir(), "user data dir missing")
        print("m2 builtin chromium live smoke ok")
        return 0
    finally:
        for session in sessions:
            provider.close_session(session, config)
        if original_data_dir is None:
            os.environ.pop("AM_DATA_DIR", None)
        else:
            os.environ["AM_DATA_DIR"] = original_data_dir
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
