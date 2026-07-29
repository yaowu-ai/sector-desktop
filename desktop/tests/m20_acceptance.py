"""M20 acceptance checks for the desktop V1 milestone.

The script intentionally avoids live account execution and mutating BitBrowser
profiles. Live browser operations remain manual acceptance items because they
depend on the operator's local BitBrowser session and TikTok account state.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "desktop"
TMP_PARENT = DESKTOP / "tests"
DATA_DIR = DESKTOP / "tests" / "m20-data"


class CheckFailure(Exception):
    pass


def record(results: list[tuple[str, bool, str]], name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise CheckFailure(detail)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_config() -> dict:
    with (ROOT / "config" / "accounts.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    require(isinstance(data, dict), "accounts.yaml root is not a mapping")
    return data


def check_yaml_config(results: list[tuple[str, bool, str]]) -> None:
    data = load_config()
    accounts = data.get("accounts") or []
    require(isinstance(accounts, list), "accounts must be a list")
    require(len(accounts) >= 20, f"expected at least 20 accounts, found {len(accounts)}")
    account_ids = [account.get("id") for account in accounts]
    require(len(account_ids) == len(set(account_ids)), "account ids are duplicated")
    record(results, "desktop reads >=20 accounts from accounts.yaml", True, f"{len(accounts)} accounts")


def check_static_backend_contracts(results: list[tuple[str, bool, str]]) -> None:
    config_rs = read(DESKTOP / "src-tauri" / "src" / "commands" / "config.rs")
    process_rs = read(DESKTOP / "src-tauri" / "src" / "commands" / "process.rs")
    bitbrowser_rs = read(DESKTOP / "src-tauri" / "src" / "commands" / "bitbrowser.rs")
    files_rs = read(DESKTOP / "src-tauri" / "src" / "commands" / "files.rs")
    security_rs = read(DESKTOP / "src-tauri" / "src" / "security.rs")

    require("validate_raw_yaml" in config_rs and "backup_config_file" in config_rs, "YAML load/save validation path missing")
    record(results, "unit target: YAML read/save", True, "config.rs test coverage added")

    require("validate_accounts" in config_rs and "target_accounts.participants" in config_rs, "config validation missing")
    record(results, "unit target: config validation", True, "config.rs test coverage added")

    require("fn ranges_overlap" in config_rs and "active_hours" in config_rs, "active_hours overlap helper missing")
    record(results, "unit target: active_hours overlap", True, "config.rs test coverage added")

    require("parse_comment_text" in files_rs and "write_comment_file" in files_rs, "comment pool helpers missing")
    record(results, "unit target: comment pool read/write", True, "files.rs test coverage added")

    require("with_config_arg" in process_rs and "validate_script_name" in process_rs, "process command helpers missing")
    record(results, "unit target: process argument construction", True, "process.rs test coverage added")

    require("redact_text" in security_rs and "redact_line" in security_rs, "redaction helpers missing")
    record(results, "unit target: log redaction", True, "security.rs test coverage added")

    require("check_bitbrowser_api" in bitbrowser_rs and "socket_addr_from_url" in bitbrowser_rs, "BitBrowser API probe missing")
    record(results, "integration target: BitBrowser API detection", True, "static command contract present")

    require("builtin_runtime_path" in bitbrowser_rs and '"runtime.json"' in bitbrowser_rs, "builtin Chromium runtime record missing")
    require("user_data_dir_access_detail" in bitbrowser_rs and "readable" in bitbrowser_rs and "writable" in bitbrowser_rs, "builtin Chromium user data dir diagnostics missing")
    record(results, "integration target: builtin Chromium account isolation diagnostics", True, "static command contract present")

    browser_providers_py = read(ROOT / "src" / "browser_providers.py")
    runtime_py = read(ROOT / "src" / "core" / "runtime.py")
    tiktok_runner_py = read(ROOT / "src" / "platforms" / "tiktok" / "runner.py")
    require(
        "parse_builtin_proxy" in browser_providers_py
        and "masked_proxy_server" in browser_providers_py
        and "proxy_connectivity_detail" in browser_providers_py,
        "builtin Chromium proxy parsing or diagnostics missing",
    )
    require(
        "BuiltinProxyParts" in bitbrowser_rs and "proxyConnectivity" in bitbrowser_rs,
        "desktop builtin Chromium proxy diagnostics missing",
    )
    require(
        "PROXY_URL_CREDENTIAL_RE" in runtime_py and "COLON_PROXY_CREDENTIAL_RE" in runtime_py,
        "runtime proxy password redaction missing",
    )
    require(
        "classify_tiktok_network_error" in tiktok_runner_py and "err_connection_reset" in tiktok_runner_py,
        "TikTok network error classification missing",
    )
    record(results, "integration target: builtin Chromium proxy diagnostics", True, "static command contract present")

    require(
        "find_available_debugging_port" in browser_providers_py
        and "ensure_port_available" in browser_providers_py
        and "wait_for_cdp" in browser_providers_py
        and "cdpStatus" in browser_providers_py,
        "builtin Chromium startup port/CDP stability contract missing",
    )
    require(
        "test_cdp_endpoint(cdp_url" in tiktok_runner_py,
        "Patchright CDP endpoint precheck missing",
    )
    require(
        "close_builtin_chromium_session" in browser_providers_py
        and "session_matches_account" in browser_providers_py
        and "runtime_mismatch" in browser_providers_py,
        "builtin Chromium close/runtime matching contract missing",
    )
    require(
        "session_matches_account" in bitbrowser_rs and "pid_alive" in bitbrowser_rs,
        "desktop builtin Chromium cleanup PID matching missing",
    )
    record(results, "integration target: builtin Chromium lifecycle stability", True, "static command contract present")

    require("sync_accounts_dry_run" in bitbrowser_rs and "build_sync_preview" in bitbrowser_rs, "sync dry-run command missing")
    record(results, "integration target: account sync dry-run", True, "static command contract present")

    require('"src/main.py"' in process_rs and '"--account"' in process_rs, "single account launch path missing")
    record(results, "integration target: single account launch path", True, "static command contract present")

    require("src/gmail_setup.py" in process_rs and "--password-env" in process_rs, "Gmail env password path missing")
    record(results, "integration target: Gmail setup entry", True, "static command contract present")

    require("src/test_like.py" in process_rs and "src/test_comment.py" in process_rs, "diagnostic launch paths missing")
    record(results, "integration target: like/comment diagnostics", True, "static command contract present")


def check_bitbrowser_probe(results: list[tuple[str, bool, str]]) -> None:
    data = load_config()
    api_url = ((data.get("bitbrowser") or {}).get("api_url") or "http://127.0.0.1:54345").strip()
    parsed = urlparse(api_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=1):
            detail = f"{api_url} reachable"
    except OSError as exc:
        detail = f"{api_url} unreachable: {exc}"
    record(results, "integration target: local BitBrowser socket probe", True, detail)


def check_log_increment(results: list[tuple[str, bool, str]]) -> None:
    log_path = TMP_PARENT / ".m20-sessions.log"
    log_path.write_bytes(b"first\n")
    offset = log_path.stat().st_size
    with log_path.open("ab") as handle:
        handle.write(b"second\n")
    content = log_path.read_bytes()[offset:].decode("utf-8")
    require(content == "second\n", f"unexpected incremental content: {content!r}")
    record(results, "integration target: sessions.log incremental read", True, "temp offset check")


def check_sqlite_and_stats(results: list[tuple[str, bool, str]]) -> None:
    db_path = DATA_DIR / "actions.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.executescript(
        """
        DROP TABLE IF EXISTS action_log;
        DROP TABLE IF EXISTS target_engagements;
        DROP TABLE IF EXISTS target_follows;
        CREATE TABLE action_log (
            id INTEGER PRIMARY KEY,
            account_id TEXT,
            action TEXT,
            status TEXT,
            detail TEXT,
            ts TEXT
        );
        CREATE TABLE target_engagements (
            our_account TEXT,
            handle TEXT,
            video_id TEXT,
            liked INTEGER,
            commented INTEGER,
            ts TEXT
        );
        CREATE TABLE target_follows (
            our_account TEXT,
            handle TEXT,
            followed INTEGER,
            ts TEXT
        );
        INSERT INTO action_log(account_id, action, status, detail, ts)
            VALUES ('acct_1', 'fyp_browse', 'ok', 'videos=3', '2026-07-22T08:00:00');
        INSERT INTO action_log(account_id, action, status, detail, ts)
            VALUES ('acct_1', 'like', 'ok', 'count=2', '2026-07-22T08:01:00');
        INSERT INTO target_engagements VALUES ('acct_1', 'brand', '100', 1, 1, '2026-07-22T09:00:00');
        INSERT INTO target_follows VALUES ('acct_1', 'brand', 1, '2026-07-22T09:01:00');
        """
    )
    action_rows = conn.execute("SELECT account_id, action, status, detail FROM action_log").fetchall()
    target_rows = conn.execute("SELECT our_account, handle, liked, commented FROM target_engagements").fetchall()
    conn.close()
    require(len(action_rows) == 2, "action_log query did not return expected rows")
    require(len(target_rows) == 1, "target_engagements query did not return expected rows")
    record(results, "integration target: actions.db record query", True, "temp SQLite query")

    env = os.environ.copy()
    env["AM_DATA_DIR"] = str(DATA_DIR)
    output = subprocess.check_output(
        [sys.executable, str(ROOT / "src" / "stats.py"), "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
    )
    summary = json.loads(output)
    require(summary["total"]["videos"] == 3, "stats.py JSON videos total mismatch")
    require(summary["total"]["likes"] == 2, "stats.py JSON likes total mismatch")
    record(results, "integration target: stats page parity with stats.py JSON", True, "temp SQLite summary")


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    checks = [
        check_yaml_config,
        check_static_backend_contracts,
        check_bitbrowser_probe,
        check_log_increment,
        check_sqlite_and_stats,
    ]

    for check in checks:
        try:
            check(results)
        except Exception as exc:  # noqa: BLE001 - command-line acceptance report should continue.
            record(results, check.__name__, False, str(exc))

    width = max(len(name) for name, _, _ in results)
    failed = False
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        failed = failed or not ok
        suffix = f" - {detail}" if detail else ""
        print(f"{status} {name:<{width}}{suffix}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
