"""Browser provider adapter layer."""
from __future__ import annotations

import os
import platform
import json
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol
from urllib.parse import urlparse

import requests
from bitbrowser import BitBrowserClient
from runtime_config import resolve_data_dir


BITBROWSER = "bitbrowser"
BUILTIN_CHROMIUM = "builtin_chromium"
DEFAULT_BROWSER_PROVIDER = BITBROWSER
VALID_BROWSER_PROVIDERS = {BITBROWSER, BUILTIN_CHROMIUM}


@dataclass(frozen=True)
class BrowserProviderCapability:
    provider: str
    label: str
    implemented: bool
    production_ready: bool
    can_launch: bool
    can_close: bool
    provides_cdp_endpoint: bool
    requires_profile_id: bool
    supports_tiktok: bool
    risk_level: str
    notes: str


@dataclass(frozen=True)
class BrowserSession:
    provider: str
    account_id: str
    profile_id: Optional[str]
    cdp_endpoint: str
    already_open: bool = False
    process_id: Optional[int] = None
    user_data_dir: Optional[str] = None


@dataclass(frozen=True)
class BuiltinChromiumCloseResult:
    account_id: str
    status: str
    detail: str


@dataclass(frozen=True)
class BuiltinProxy:
    scheme: str
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def server_arg(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def masked(self) -> str:
        if self.username or self.password:
            return f"{self.scheme}://{self.username}:***@{self.host}:{self.port}"
        return f"{self.scheme}://{self.host}:{self.port}"


def windows_subprocess_kwargs(*, new_process_group: bool = False) -> Dict[str, Any]:
    if os.name != "nt":
        return {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if new_process_group:
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": creationflags,
        "startupinfo": startupinfo,
    }


@dataclass(frozen=True)
class BrowserProviderStatus:
    provider: str
    available: bool
    message: str
    api_url: Optional[str] = None


class BrowserProvider(Protocol):
    name: str
    capability: BrowserProviderCapability

    def status(self, config: Mapping[str, Any]) -> BrowserProviderStatus:
        ...

    def validate_account(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        ...

    def is_open(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
        ...

    def start_session(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> BrowserSession:
        ...

    def close_session(self, session: BrowserSession, config: Mapping[str, Any]) -> None:
        ...


PROVIDER_CAPABILITIES = {
    BITBROWSER: BrowserProviderCapability(
        provider=BITBROWSER,
        label="BitBrowser",
        implemented=True,
        production_ready=True,
        can_launch=True,
        can_close=True,
        provides_cdp_endpoint=True,
        requires_profile_id=True,
        supports_tiktok=True,
        risk_level="stable",
        notes="Production default. Uses BitBrowser Local API and existing bitbrowser_profile_id.",
    ),
    BUILTIN_CHROMIUM: BrowserProviderCapability(
        provider=BUILTIN_CHROMIUM,
        label="Built-in Chromium",
        implemented=True,
        production_ready=True,
        can_launch=True,
        can_close=True,
        provides_cdp_endpoint=True,
        requires_profile_id=False,
        supports_tiktok=True,
        risk_level="production_optional",
        notes=(
            "Production optional. Launches local Chromium with a per-account user data dir "
            "and a temporary CDP port. It is not an equivalent replacement for BitBrowser "
            "fingerprint capabilities; BitBrowser remains the default recommendation."
        ),
    ),
}


CDP_STARTUP_HINT = (
    "A Chromium debugging endpoint such as http://127.0.0.1:<port> is required."
)


class BitBrowserProvider:
    name = BITBROWSER
    capability = PROVIDER_CAPABILITIES[BITBROWSER]

    def status(self, config: Mapping[str, Any]) -> BrowserProviderStatus:
        api_url = bitbrowser_api_url(config)
        try:
            BitBrowserClient(api_url).list_browsers(page_size=1, timeout=5)
            return BrowserProviderStatus(
                provider=self.name,
                available=True,
                message="BitBrowser Local API is available",
                api_url=api_url,
            )
        except Exception as exc:
            return BrowserProviderStatus(
                provider=self.name,
                available=False,
                message=f"{type(exc).__name__}: {exc}",
                api_url=api_url,
            )

    def validate_account(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        profile_id = bitbrowser_profile_id(account)
        if not profile_id:
            raise ValueError(f"{account.get('id', '<unknown>')} missing bitbrowser_profile_id")
        api_url = bitbrowser_api_url(config)
        if not api_url:
            raise ValueError("bitbrowser.api_url is required")

    def is_open(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
        self.validate_account(account, config)
        return BitBrowserClient(bitbrowser_api_url(config)).is_open(bitbrowser_profile_id(account))

    def start_session(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> BrowserSession:
        self.validate_account(account, config)
        account_id = str(account.get("id", ""))
        profile_id = bitbrowser_profile_id(account)
        client = BitBrowserClient(bitbrowser_api_url(config))
        already_open = client.is_open(profile_id)
        cdp_endpoint = client.open_browser(profile_id)
        return BrowserSession(
            provider=self.name,
            account_id=account_id,
            profile_id=profile_id,
            cdp_endpoint=cdp_endpoint,
            already_open=already_open,
        )

    def close_session(self, session: BrowserSession, config: Mapping[str, Any]) -> None:
        if session.profile_id:
            BitBrowserClient(bitbrowser_api_url(config)).close_browser(session.profile_id)


class ReservedProvider:
    def __init__(self, name: str):
        self.name = name
        self.capability = PROVIDER_CAPABILITIES[name]

    def status(self, config: Mapping[str, Any]) -> BrowserProviderStatus:
        return BrowserProviderStatus(
            provider=self.name,
            available=False,
            message=f"{self.capability.label} is reserved and not implemented",
        )

    def validate_account(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        raise NotImplementedError(f"browser provider '{self.name}' is not implemented")

    def is_open(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
        self.validate_account(account, config)
        return False

    def start_session(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> BrowserSession:
        self.validate_account(account, config)
        raise NotImplementedError(f"browser provider '{self.name}' is not implemented")

    def close_session(self, session: BrowserSession, config: Mapping[str, Any]) -> None:
        return None


class BuiltinChromiumProvider:
    name = BUILTIN_CHROMIUM
    capability = PROVIDER_CAPABILITIES[BUILTIN_CHROMIUM]

    def status(self, config: Mapping[str, Any]) -> BrowserProviderStatus:
        try:
            executable = chromium_executable_path(config)
            return BrowserProviderStatus(
                provider=self.name,
                available=True,
                message=f"Chromium executable found: {executable}",
                api_url=executable,
            )
        except Exception as exc:
            return BrowserProviderStatus(
                provider=self.name,
                available=False,
                message=f"{exc}. Configure browser.chromium_executable or AM_CHROMIUM_EXECUTABLE.",
            )

    def validate_account(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        chromium_executable_path(config)
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            raise ValueError("builtin_chromium requires a non-empty account id")
        try:
            proxy = builtin_proxy_config(account)
            if proxy:
                proxy_server_arg(proxy)
        except ValueError as exc:
            raise ValueError(f"{account_id}.browser.proxy: {exc}") from exc

    def is_open(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
        session = read_builtin_session(account)
        return bool(session_matches_account(account, session) and pid_alive(session_pid(session)))

    def start_session(self, account: Mapping[str, Any], config: Mapping[str, Any]) -> BrowserSession:
        self.validate_account(account, config)
        account_id = str(account["id"])
        executable = chromium_executable_path(config)
        user_data = builtin_user_data_dir(account)
        user_data.mkdir(parents=True, exist_ok=True)
        recover_builtin_chromium_session(account)
        port = find_available_debugging_port()
        cdp_endpoint = f"http://127.0.0.1:{port}"

        command = [
            executable,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={str(user_data)}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-popup-blocking",
            "about:blank",
        ]
        proxy = builtin_proxy_config(account)
        if proxy:
            parsed_proxy = parse_builtin_proxy(proxy)
            if parsed_proxy.username or parsed_proxy.password:
                extension_dir = write_builtin_proxy_auth_extension(user_data, parsed_proxy)
                command.insert(-1, f"--disable-extensions-except={extension_dir}")
                command.insert(-1, f"--load-extension={extension_dir}")
            else:
                command.insert(-1, f"--proxy-server={parsed_proxy.server_arg}")

        process = None
        startup_context = builtin_startup_context(account, executable, port, user_data, proxy)
        try:
            ensure_port_available(port)
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **windows_subprocess_kwargs(new_process_group=True),
            )
            cdp_version = wait_for_cdp(cdp_endpoint)
        except Exception as exc:
            if process is not None:
                terminate_pid(process.pid)
            raise RuntimeError(f"failed to start builtin_chromium: {startup_context}; error={exc}") from exc

        record_builtin_session(account, process.pid, cdp_endpoint, user_data, executable, cdp_version)
        return BrowserSession(
            provider=self.name,
            account_id=account_id,
            profile_id=account_id,
            cdp_endpoint=cdp_endpoint,
            already_open=False,
            process_id=process.pid,
            user_data_dir=str(user_data),
        )

    def close_session(self, session: BrowserSession, config: Mapping[str, Any]) -> BuiltinChromiumCloseResult:
        return close_builtin_chromium_session(session)


PROVIDERS: Dict[str, BrowserProvider] = {
    BITBROWSER: BitBrowserProvider(),
    BUILTIN_CHROMIUM: BuiltinChromiumProvider(),
}


def normalize_provider_name(value: Optional[str]) -> str:
    provider = str(value or DEFAULT_BROWSER_PROVIDER).strip().lower()
    if not provider:
        provider = DEFAULT_BROWSER_PROVIDER
    if provider not in VALID_BROWSER_PROVIDERS:
        raise ValueError(f"unsupported browser provider '{value}'")
    return provider


def default_provider(config: Mapping[str, Any]) -> str:
    browser = config.get("browser") if isinstance(config, Mapping) else None
    if isinstance(browser, Mapping):
        value = browser.get("default_provider")
        if value:
            return normalize_provider_name(value)
    return DEFAULT_BROWSER_PROVIDER


def account_provider_name(account: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    if "browser_provider" in account and account.get("browser_provider"):
        return normalize_provider_name(account.get("browser_provider"))
    browser = account.get("browser")
    if isinstance(browser, Mapping) and browser.get("provider"):
        return normalize_provider_name(browser.get("provider"))
    return default_provider(config)


def get_provider(name: str) -> BrowserProvider:
    return PROVIDERS[normalize_provider_name(name)]


def provider_for_account(account: Mapping[str, Any], config: Mapping[str, Any]) -> BrowserProvider:
    return get_provider(account_provider_name(account, config))


def bitbrowser_api_url(config: Mapping[str, Any]) -> str:
    bitbrowser = config.get("bitbrowser") if isinstance(config, Mapping) else None
    if isinstance(bitbrowser, Mapping):
        value = str(bitbrowser.get("api_url") or "").strip()
        if value:
            return value
    return "http://127.0.0.1:54345"


def bitbrowser_profile_id(account: Mapping[str, Any]) -> Optional[str]:
    browser = account.get("browser")
    if isinstance(browser, Mapping):
        value = str(browser.get("profile_id") or "").strip()
        if value:
            return value
        bitbrowser = browser.get("bitbrowser")
        if isinstance(bitbrowser, Mapping):
            value = str(bitbrowser.get("profile_id") or "").strip()
            if value:
                return value
    value = str(account.get("bitbrowser_profile_id") or "").strip()
    return value or None


def browser_defaults(config: Mapping[str, Any]) -> Mapping[str, Any]:
    browser = config.get("browser") if isinstance(config, Mapping) else None
    return browser if isinstance(browser, Mapping) else {}


def builtin_chromium_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    browser = browser_defaults(config)
    builtin = browser.get("builtin_chromium")
    if isinstance(builtin, Mapping):
        return builtin
    builtin = config.get("builtin_chromium") if isinstance(config, Mapping) else None
    return builtin if isinstance(builtin, Mapping) else {}


def chromium_executable_path(config: Mapping[str, Any]) -> str:
    candidates = []
    browser = browser_defaults(config)
    builtin = builtin_chromium_config(config)
    for value in (
        os.environ.get("AM_CHROMIUM_EXECUTABLE"),
        browser.get("chromium_executable"),
        browser.get("chromium_executable_path"),
        builtin.get("executable_path"),
        builtin.get("chromium_executable"),
    ):
        if value:
            candidates.append(str(value).strip())

    if os.name == "nt":
        program_files = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for root in filter(None, program_files):
            candidates.extend(
                [
                    str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"),
                    str(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
                    str(Path(root) / "Chromium" / "Application" / "chrome.exe"),
                ]
            )
    elif platform.system() == "Darwin":
        home = Path.home()
        for root in (Path("/Applications"), home / "Applications"):
            candidates.extend(
                [
                    str(root / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome"),
                    str(
                        root
                        / "Google Chrome for Testing.app"
                        / "Contents"
                        / "MacOS"
                        / "Google Chrome for Testing"
                    ),
                    str(root / "Microsoft Edge.app" / "Contents" / "MacOS" / "Microsoft Edge"),
                    str(root / "Chromium.app" / "Contents" / "MacOS" / "Chromium"),
                ]
            )
        for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "msedge"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    else:
        for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "msedge"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for candidate in candidates:
        path = resolve_chromium_candidate(Path(candidate).expanduser())
        if path:
            return str(path)
    raise FileNotFoundError("builtin_chromium could not find a Chromium/Chrome/Edge executable")


def resolve_chromium_candidate(path: Path) -> Optional[Path]:
    if path.is_file():
        return path
    if platform.system() == "Darwin" and path.suffix == ".app" and path.is_dir():
        macos_dir = path / "Contents" / "MacOS"
        names = [
            path.stem,
            "Google Chrome",
            "Google Chrome for Testing",
            "Microsoft Edge",
            "Chromium",
        ]
        for name in names:
            executable = macos_dir / name
            if executable.is_file():
                return executable
    return None


def safe_account_dir_name(account_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(account_id).strip())
    return value or "account"


def builtin_base_dir() -> Path:
    return resolve_data_dir() / "browser" / BUILTIN_CHROMIUM


def builtin_account_dir(account_or_id: Any) -> Path:
    account_id = account_or_id.get("id") if isinstance(account_or_id, Mapping) else account_or_id
    return builtin_base_dir() / safe_account_dir_name(str(account_id))


def builtin_user_data_dir(account: Mapping[str, Any]) -> Path:
    browser = account.get("browser")
    if isinstance(browser, Mapping):
        value = str(browser.get("user_data_dir") or "").strip()
        if value:
            path = Path(value).expanduser()
            return path if path.is_absolute() else resolve_data_dir() / path
    return builtin_account_dir(account) / "user-data"


def builtin_session_path(account_or_id: Any) -> Path:
    return builtin_account_dir(account_or_id) / "runtime.json"


def legacy_builtin_session_path(account_or_id: Any) -> Path:
    return builtin_account_dir(account_or_id) / "session.json"


def record_builtin_session(
    account: Mapping[str, Any],
    pid: int,
    cdp_endpoint: str,
    user_data_dir: Path,
    executable: str,
    cdp_version: Optional[Mapping[str, Any]] = None,
) -> None:
    path = builtin_session_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    port = endpoint_port(cdp_endpoint)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    cdp_status = {
        "browser": cdp_version.get("Browser") if isinstance(cdp_version, Mapping) else None,
        "protocolVersion": cdp_version.get("Protocol-Version") if isinstance(cdp_version, Mapping) else None,
        "webSocketDebuggerUrl": cdp_version.get("webSocketDebuggerUrl") if isinstance(cdp_version, Mapping) else None,
    }
    path.write_text(
        json.dumps(
            {
                "accountId": account.get("id"),
                "lastPid": pid,
                "lastPort": port,
                "lastCdpEndpoint": cdp_endpoint,
                "userDataDir": str(user_data_dir),
                "lastStartedAt": started_at,
                "cdpStatus": cdp_status,
                "provider": BUILTIN_CHROMIUM,
                "account_id": account.get("id"),
                "pid": pid,
                "port": port,
                "cdp_endpoint": cdp_endpoint,
                "user_data_dir": str(user_data_dir),
                "executable": executable,
                "started_at": started_at,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_builtin_session(account_or_id: Any) -> Optional[Mapping[str, Any]]:
    for path in (builtin_session_path(account_or_id), legacy_builtin_session_path(account_or_id)):
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def clear_builtin_session(account_or_id: Any) -> bool:
    cleared = True
    for path in (builtin_session_path(account_or_id), legacy_builtin_session_path(account_or_id)):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            cleared = False
    return cleared


def endpoint_port(endpoint: str) -> Optional[int]:
    try:
        return urlparse(endpoint).port
    except Exception:
        return None


def session_pid(session: Optional[Mapping[str, Any]]) -> Optional[int]:
    if not isinstance(session, Mapping):
        return None
    value = session.get("lastPid", session.get("pid"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def session_cdp_endpoint(session: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(session, Mapping):
        return None
    value = session.get("lastCdpEndpoint", session.get("cdp_endpoint"))
    return str(value).strip() if value else None


def session_matches_account(account_or_id: Any, session: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(session, Mapping):
        return False
    account_id = account_or_id.get("id") if isinstance(account_or_id, Mapping) else account_or_id
    recorded_account = session.get("accountId", session.get("account_id"))
    provider = session.get("provider", BUILTIN_CHROMIUM)
    return str(recorded_account or "") == str(account_id or "") and provider == BUILTIN_CHROMIUM


def user_data_dir_access_detail(path: Path) -> tuple[str, str]:
    detail_path = str(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return "error", f"path={detail_path}; exists={path.exists()}; readable=false; writable=false; error={exc}"

    readable = path.is_dir() and os.access(path, os.R_OK)
    writable = path.is_dir() and os.access(path, os.W_OK)
    test_file = path / ".account-matrix-write-test"
    if writable:
        try:
            test_file.write_text("ok", encoding="utf-8")
        except Exception:
            writable = False
        else:
            try:
                test_file.unlink(missing_ok=True)
            except Exception:
                pass

    status = "ok" if readable and writable else "error"
    return status, f"path={detail_path}; exists={path.exists()}; readable={str(readable).lower()}; writable={str(writable).lower()}"


def pid_alive(pid: Any) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                **windows_subprocess_kwargs(),
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_pid(pid: Any) -> None:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                **windows_subprocess_kwargs(),
            )
        else:
            os.kill(pid, 15)
    except Exception:
        pass


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.bind((host, int(port)))
            return True
        except OSError:
            return False


def ensure_port_available(port: int) -> None:
    if not port_available(port):
        raise RuntimeError(f"debugging port {port} is already in use")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def find_available_debugging_port(attempts: int = 10) -> int:
    last_port = None
    for _ in range(attempts):
        port = find_free_port()
        last_port = port
        if port_available(port):
            return port
    raise RuntimeError(f"could not find an available Chromium debugging port; last candidate={last_port}")


def wait_for_cdp(endpoint: str, timeout: int = 20) -> Mapping[str, Any]:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            return test_cdp_endpoint(endpoint, timeout=2)
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"builtin_chromium did not expose CDP endpoint {endpoint}: {last_error}")


def builtin_proxy_config(account: Mapping[str, Any]) -> Optional[Mapping[str, str]]:
    browser = account.get("browser")
    if not isinstance(browser, Mapping):
        return None
    raw = str(browser.get("proxy") or "").strip()
    if not raw:
        return None
    proxy_type = str(browser.get("proxy_type") or "socks5").strip().lower()
    if proxy_type not in {"http", "https", "socks5"}:
        raise ValueError("browser.proxy_type must be http, https, or socks5")
    return {"proxy": raw, "proxy_type": proxy_type}


def proxy_server_arg(proxy: Mapping[str, str]) -> str:
    return parse_builtin_proxy(proxy).server_arg


def parse_builtin_proxy(proxy: Mapping[str, str]) -> BuiltinProxy:
    raw = str(proxy["proxy"]).strip()
    proxy_type = str(proxy.get("proxy_type") or "socks5").strip().lower()
    if proxy_type not in {"http", "https", "socks5"}:
        raise ValueError("browser.proxy_type must be http, https, or socks5")
    if "://" in raw:
        parsed = urlparse(raw)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https", "socks5"}:
            raise ValueError("browser.proxy scheme must be http, https, or socks5")
        if not parsed.hostname:
            raise ValueError("browser.proxy URL must include a host")
        if parsed.port is None or parsed.port <= 0:
            raise ValueError("browser.proxy port must be between 1 and 65535")
        return BuiltinProxy(
            scheme=scheme,
            host=parsed.hostname,
            port=parsed.port,
            username=parsed.username or "",
            password=parsed.password or "",
        )

    parts = raw.split(":")
    if len(parts) == 2:
        host, port = parts
        return BuiltinProxy(scheme=proxy_type, host=_validate_proxy_host(host), port=_validate_proxy_port(port))
    if len(parts) == 4:
        host, port, username, password = parts
        if not username.strip() or not password.strip():
            raise ValueError("browser.proxy username and password must be non-empty")
        return BuiltinProxy(
            scheme=proxy_type,
            host=_validate_proxy_host(host),
            port=_validate_proxy_port(port),
            username=username.strip(),
            password=password.strip(),
        )
    raise ValueError("browser.proxy must be host:port or host:port:username:password")


def _validate_proxy_host(host: str) -> str:
    value = str(host or "").strip()
    if not value:
        raise ValueError("browser.proxy host must be non-empty")
    return value


def _validate_proxy_port(port: str) -> int:
    try:
        value = int(str(port).strip())
    except ValueError as exc:
        raise ValueError("browser.proxy port must be between 1 and 65535") from exc
    if value <= 0 or value > 65535:
        raise ValueError("browser.proxy port must be between 1 and 65535")
    return value


def write_builtin_proxy_auth_extension(user_data_dir: Path, proxy: BuiltinProxy) -> Path:
    extension_dir = user_data_dir / "proxy-auth-extension"
    extension_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "manifest_version": 2,
        "name": "星域 Proxy Auth",
        "version": "1.0.0",
        "permissions": [
            "proxy",
            "webRequest",
            "webRequestBlocking",
            "<all_urls>",
        ],
        "background": {"scripts": ["background.js"]},
    }
    background = f"""
const proxyConfig = {{
  mode: "fixed_servers",
  rules: {{
    singleProxy: {{
      scheme: {json.dumps(proxy.scheme)},
      host: {json.dumps(proxy.host)},
      port: {proxy.port}
    }},
    bypassList: ["localhost", "127.0.0.1", "::1"]
  }}
}};

chrome.proxy.settings.set({{ value: proxyConfig, scope: "regular" }});

chrome.webRequest.onAuthRequired.addListener(
  () => ({{
    authCredentials: {{
      username: {json.dumps(proxy.username)},
      password: {json.dumps(proxy.password)}
    }}
  }}),
  {{ urls: ["<all_urls>"] }},
  ["blocking"]
);
""".strip()
    (extension_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    (extension_dir / "background.js").write_text(background, encoding="utf-8")
    return extension_dir


def masked_proxy_server(proxy: Mapping[str, str]) -> str:
    return parse_builtin_proxy(proxy).masked


def proxy_connectivity_detail(proxy: Mapping[str, str], timeout: float = 3) -> tuple[str, str]:
    parsed = parse_builtin_proxy(proxy)
    try:
        with socket.create_connection((parsed.host, parsed.port), timeout=timeout):
            pass
        return "ok", f"{parsed.masked}; host={parsed.host}; port={parsed.port}; reachable=true"
    except OSError as exc:
        return "error", f"{parsed.masked}; host={parsed.host}; port={parsed.port}; reachable=false; error={exc}"


def builtin_startup_context(
    account: Mapping[str, Any],
    executable: str,
    port: int,
    user_data_dir: Path,
    proxy: Optional[Mapping[str, str]],
) -> str:
    account_id = account.get("id")
    proxy_detail = "not configured"
    if proxy:
        try:
            proxy_detail = masked_proxy_server(proxy)
        except Exception as exc:
            proxy_detail = f"invalid proxy: {exc}"
    return (
        f"account_id={account_id}; provider={BUILTIN_CHROMIUM}; port={port}; "
        f"executable={executable}; user_data_dir={user_data_dir}; proxy={proxy_detail}"
    )


def recover_builtin_chromium_session(account: Mapping[str, Any]) -> Optional[BuiltinChromiumCloseResult]:
    session = read_builtin_session(account)
    if not session:
        return None
    pid = session_pid(session)
    if not session_matches_account(account, session):
        return BuiltinChromiumCloseResult(
            account_id=str(account.get("id") or ""),
            status="runtime_mismatch",
            detail="existing builtin_chromium runtime record does not match this account; left untouched",
        )
    if not pid_alive(pid):
        cleared = clear_builtin_session(account)
        return BuiltinChromiumCloseResult(
            account_id=str(account.get("id") or ""),
            status="already_exited",
            detail=f"stale runtime {'cleared' if cleared else 'clear failed'}; pid={pid}",
        )

    terminate_pid(pid)
    cleared = clear_builtin_session(account)
    return BuiltinChromiumCloseResult(
        account_id=str(account.get("id") or ""),
        status="closed_residual",
        detail=f"closed residual builtin_chromium process from runtime; pid={pid}; runtime {'cleared' if cleared else 'clear failed'}",
    )


def close_builtin_chromium_session(session: BrowserSession) -> BuiltinChromiumCloseResult:
    account_id = session.account_id
    runtime = read_builtin_session(account_id)
    pid = session.process_id
    if not pid:
        cleared = clear_builtin_session(account_id)
        return BuiltinChromiumCloseResult(
            account_id=account_id,
            status="no_pid",
            detail=f"session had no process id; runtime {'cleared' if cleared else 'clear failed'}",
        )
    if not runtime:
        if pid_alive(pid):
            return BuiltinChromiumCloseResult(
                account_id=account_id,
                status="runtime_missing",
                detail=f"runtime record missing; process pid={pid} left untouched",
            )
        cleared = clear_builtin_session(account_id)
        return BuiltinChromiumCloseResult(
            account_id=account_id,
            status="already_exited",
            detail=f"runtime record missing and process already exited; pid={pid}; runtime {'cleared' if cleared else 'clear failed'}",
        )
    runtime_pid = session_pid(runtime)
    runtime_cdp = session_cdp_endpoint(runtime)
    if (
        not session_matches_account(account_id, runtime)
        or runtime_pid != int(pid)
        or (session.cdp_endpoint and runtime_cdp != session.cdp_endpoint)
    ):
        return BuiltinChromiumCloseResult(
            account_id=account_id,
            status="runtime_mismatch",
            detail=(
                f"runtime record did not match session; expected pid={pid}, cdp={session.cdp_endpoint}; "
                f"runtime pid={runtime_pid}, cdp={runtime_cdp}; process left untouched"
            ),
        )
    if not pid_alive(pid):
        cleared = clear_builtin_session(account_id)
        return BuiltinChromiumCloseResult(
            account_id=account_id,
            status="already_exited",
            detail=f"browser process already exited; pid={pid}; runtime {'cleared' if cleared else 'clear failed'}",
        )

    terminate_pid(pid)
    cleared = clear_builtin_session(account_id)
    return BuiltinChromiumCloseResult(
        account_id=account_id,
        status="closed",
        detail=f"closed builtin_chromium process pid={pid}; runtime {'cleared' if cleared else 'clear failed'}",
    )


def normalize_cdp_endpoint(endpoint: Optional[str]) -> str:
    value = str(endpoint or "").strip().rstrip("/")
    if not value:
        raise ValueError(f"CDP endpoint is required. {CDP_STARTUP_HINT}")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "ws"}:
        raise ValueError(f"CDP endpoint must use http:// or ws://, got '{value}'. {CDP_STARTUP_HINT}")
    if not parsed.hostname:
        raise ValueError(f"CDP endpoint is missing host: '{value}'. {CDP_STARTUP_HINT}")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"CDP endpoint must point to localhost, got '{value}'. {CDP_STARTUP_HINT}")
    if parsed.port is None:
        raise ValueError(f"CDP endpoint must include a debugging port, got '{value}'. {CDP_STARTUP_HINT}")
    return value


def cdp_http_base(endpoint: str) -> str:
    value = normalize_cdp_endpoint(endpoint)
    parsed = urlparse(value)
    authority = parsed.netloc
    return f"http://{authority}"


def test_cdp_endpoint(endpoint: str, timeout: int = 5) -> Mapping[str, Any]:
    endpoint = normalize_cdp_endpoint(endpoint)
    try:
        response = requests.get(f"{cdp_http_base(endpoint)}/json/version", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to test CDP endpoint '{endpoint}': {exc}. Check endpoint/port/startup args.") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"CDP endpoint '{endpoint}' /json/version returned an invalid response.")
    return payload


def provider_capability_matrix():
    return [capability.__dict__.copy() for capability in PROVIDER_CAPABILITIES.values()]


def diagnose_account_browser(account: Mapping[str, Any], config: Mapping[str, Any]):
    provider = provider_for_account(account, config)
    checks = []
    try:
        provider.validate_account(account, config)
        checks.append({"name": "accountConfig", "status": "ok", "detail": provider.name})
    except Exception as exc:
        checks.append({"name": "accountConfig", "status": "error", "detail": str(exc)})

    status = provider.status(config)
    checks.append(
        {
            "name": "providerStatus",
            "status": "ok" if status.available else "error",
            "detail": status.message,
        }
    )
    if provider.name == BUILTIN_CHROMIUM:
        try:
            proxy = builtin_proxy_config(account)
            if proxy:
                checks.append({"name": "proxyConfig", "status": "ok", "detail": masked_proxy_server(proxy)})
                connectivity_status, connectivity_detail = proxy_connectivity_detail(proxy)
                checks.append(
                    {"name": "proxyConnectivity", "status": connectivity_status, "detail": connectivity_detail}
                )
            else:
                checks.append({"name": "proxyConfig", "status": "ok", "detail": "not configured"})
        except Exception as exc:
            checks.append({"name": "proxyConfig", "status": "error", "detail": str(exc)})
        user_data_dir = builtin_user_data_dir(account)
        access_status, access_detail = user_data_dir_access_detail(user_data_dir)
        checks.append({"name": "userDataDir", "status": access_status, "detail": access_detail})
        runtime_path = builtin_session_path(account)
        session = read_builtin_session(account)
        if session:
            runtime_detail = (
                f"path={runtime_path}; pid={session.get('lastPid') or session.get('pid')}; "
                f"port={session.get('lastPort') or session.get('port')}; "
                f"cdp={session.get('lastCdpEndpoint') or session.get('cdp_endpoint')}"
            )
            checks.append({"name": "runtimeRecord", "status": "ok", "detail": runtime_detail})
        else:
            checks.append({"name": "runtimeRecord", "status": "ok", "detail": f"path={runtime_path}; absent"})
    return {
        "provider": provider.name,
        "accountId": account.get("id"),
        "status": "error" if any(check["status"] == "error" for check in checks) else "ok",
        "checks": checks,
    }
