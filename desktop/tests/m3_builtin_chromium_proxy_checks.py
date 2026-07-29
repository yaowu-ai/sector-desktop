from __future__ import annotations

import os
import shutil
import socket
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import browser_providers as providers  # noqa: E402
from core.runtime import redact_runtime_text  # noqa: E402
from platforms.tiktok.runner import classify_tiktok_network_error, tiktok_network_error_detail  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    original_data_dir = os.environ.get("AM_DATA_DIR")
    temp_root = ROOT / "desktop" / "tests" / f".m3-temp-{uuid.uuid4().hex}"
    temp_root.mkdir(parents=True)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        os.environ["AM_DATA_DIR"] = str(temp_root)

        for proxy_type in ("http", "https", "socks5"):
            proxy = {"proxy": "127.0.0.1:7890", "proxy_type": proxy_type}
            require(
                providers.proxy_server_arg(proxy) == f"{proxy_type}://127.0.0.1:7890",
                f"{proxy_type} proxy server arg mismatch",
            )

        credential_proxy = {"proxy": "127.0.0.1:7890:user1:secret123", "proxy_type": "socks5"}
        require(
            providers.proxy_server_arg(credential_proxy) == "socks5://user1:secret123@127.0.0.1:7890",
            "credential proxy server arg mismatch",
        )
        require(
            providers.masked_proxy_server(credential_proxy) == "socks5://user1:***@127.0.0.1:7890",
            "credential proxy was not masked",
        )

        redacted = redact_runtime_text(
            "proxy=127.0.0.1:7890:user1:secret123 --proxy-server=socks5://user1:secret123@127.0.0.1:7890"
        )
        require("secret123" not in redacted, f"proxy password leaked after redaction: {redacted}")

        fake_executable = temp_root / "chrome.exe"
        fake_executable.write_bytes(b"")
        bad_account = {
            "id": "acct_proxy_bad",
            "browser_provider": "builtin_chromium",
            "browser": {"provider": "builtin_chromium", "proxy": "127.0.0.1:not-a-port"},
        }
        try:
            providers.BuiltinChromiumProvider().validate_account(
                bad_account,
                {"browser": {"chromium_executable": str(fake_executable)}},
            )
        except ValueError as exc:
            require("acct_proxy_bad.browser.proxy" in str(exc), f"proxy error did not include account field: {exc}")
        else:
            raise AssertionError("invalid proxy did not block builtin Chromium startup")

        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        status, detail = providers.proxy_connectivity_detail(
            {"proxy": f"127.0.0.1:{port}:user1:secret123", "proxy_type": "http"},
            timeout=1,
        )
        require(status == "ok", f"local proxy TCP connectivity check failed: {detail}")
        require("secret123" not in detail and "reachable=true" in detail, f"bad connectivity detail: {detail}")

        reset_error = RuntimeError("net::ERR_CONNECTION_RESET at https://www.tiktok.com/foryou")
        timeout_error = TimeoutError("page.goto timed out after 60000ms")
        dns_error = RuntimeError("net::ERR_NAME_NOT_RESOLVED")
        proxy_error = RuntimeError("net::ERR_PROXY_CONNECTION_FAILED socks5://user1:secret123@127.0.0.1:7890")
        require(classify_tiktok_network_error(reset_error) == "connection_reset", "connection reset not classified")
        require(classify_tiktok_network_error(timeout_error) == "timeout", "timeout not classified")
        require(classify_tiktok_network_error(dns_error) == "dns", "DNS not classified")
        require(classify_tiktok_network_error(proxy_error) == "proxy_failed", "proxy failure not classified")
        proxy_detail = tiktok_network_error_detail(proxy_error)
        require("category=proxy_failed" in proxy_detail, f"missing proxy category: {proxy_detail}")
        require("secret123" not in proxy_detail, f"TikTok network detail leaked proxy password: {proxy_detail}")

        print("m3 builtin chromium proxy checks ok")
        return 0
    finally:
        listener.close()
        if original_data_dir is None:
            os.environ.pop("AM_DATA_DIR", None)
        else:
            os.environ["AM_DATA_DIR"] = original_data_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
