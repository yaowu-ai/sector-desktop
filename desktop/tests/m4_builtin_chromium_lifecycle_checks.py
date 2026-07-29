from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import browser_providers as providers  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class CdpHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API.
        if self.path != "/json/version":
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "Browser": "Chrome/127.0.0.1",
            "Protocol-Version": "1.3",
            "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/test",
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def main() -> int:
    original_data_dir = os.environ.get("AM_DATA_DIR")
    temp_root = ROOT / "desktop" / "tests" / f".m4-temp-{uuid.uuid4().hex}"
    temp_root.mkdir(parents=True)
    server = HTTPServer(("127.0.0.1", 0), CdpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        os.environ["AM_DATA_DIR"] = str(temp_root)
        account = {
            "id": "acct_m4",
            "browser_provider": "builtin_chromium",
            "browser": {"provider": "builtin_chromium", "proxy": "127.0.0.1:7890:user1:secret123"},
        }

        port = providers.find_available_debugging_port()
        require(providers.port_available(port), f"selected debugging port is not available: {port}")

        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        occupied_port = occupied.getsockname()[1]
        try:
            providers.ensure_port_available(occupied_port)
        except RuntimeError as exc:
            require("already in use" in str(exc), f"occupied port error was not clear: {exc}")
        else:
            raise AssertionError("occupied port was not detected before startup")

        cdp_port = server.server_address[1]
        endpoint = f"http://127.0.0.1:{cdp_port}"
        cdp_status = providers.wait_for_cdp(endpoint, timeout=2)
        require(cdp_status["Browser"] == "Chrome/127.0.0.1", "CDP /json/version payload not returned")

        user_data_dir = providers.builtin_user_data_dir(account)
        providers.record_builtin_session(
            account,
            pid=987654,
            cdp_endpoint=endpoint,
            user_data_dir=user_data_dir,
            executable="C:/Chromium/chrome.exe",
            cdp_version=cdp_status,
        )
        runtime = providers.read_builtin_session(account)
        require(runtime["lastPort"] == cdp_port, "runtime did not record CDP port")
        require(runtime["cdpStatus"]["browser"] == "Chrome/127.0.0.1", "runtime did not record CDP status")

        close_result = providers.close_builtin_chromium_session(
            providers.BrowserSession(
                provider="builtin_chromium",
                account_id="acct_m4",
                profile_id="acct_m4",
                cdp_endpoint=endpoint,
                process_id=987654,
            )
        )
        require(close_result.status == "already_exited", f"dead process close status mismatch: {close_result}")
        runtime_after_close = providers.read_builtin_session(account)
        require(
            runtime_after_close is None or "runtime clear failed" in close_result.detail,
            "dead process close did not report runtime cleanup",
        )

        mismatch_path = providers.builtin_session_path(account)
        mismatch_path.parent.mkdir(parents=True, exist_ok=True)
        mismatch_path.write_text(
            json.dumps(
                {
                    "accountId": "acct_m4_other",
                    "provider": "builtin_chromium",
                    "lastPid": os.getpid(),
                    "lastCdpEndpoint": endpoint,
                }
            ),
            encoding="utf-8",
        )
        mismatch_result = providers.close_builtin_chromium_session(
            providers.BrowserSession(
                provider="builtin_chromium",
                account_id="acct_m4",
                profile_id="acct_m4",
                cdp_endpoint=endpoint,
                process_id=os.getpid(),
            )
        )
        require(mismatch_result.status == "runtime_mismatch", "runtime mismatch did not block process termination")
        require(mismatch_path.exists(), "runtime mismatch should leave record untouched")

        startup_context = providers.builtin_startup_context(
            account,
            "C:/Chromium/chrome.exe",
            45123,
            user_data_dir,
            providers.builtin_proxy_config(account),
        )
        require("account_id=acct_m4" in startup_context, f"startup context missing account: {startup_context}")
        require("provider=builtin_chromium" in startup_context, f"startup context missing provider: {startup_context}")
        require("port=45123" in startup_context, f"startup context missing port: {startup_context}")
        require("secret123" not in startup_context, f"startup context leaked proxy password: {startup_context}")

        print("m4 builtin chromium lifecycle checks ok")
        return 0
    finally:
        occupied.close()
        server.shutdown()
        server.server_close()
        if original_data_dir is None:
            os.environ.pop("AM_DATA_DIR", None)
        else:
            os.environ["AM_DATA_DIR"] = original_data_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
