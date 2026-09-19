"""Small ixBrowser Local API adapter used by the browser provider layer."""
from __future__ import annotations

from urllib.parse import urlsplit

try:
    from ixbrowser_local_api import IXBrowserClient as SDKClient
    from ixbrowser_local_api import Preference, Profile, Proxy
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    SDKClient = None
    Preference = None
    Profile = None
    Proxy = None


DEFAULT_API_URL = "http://127.0.0.1:53200"


def _api_target(api_url):
    value = str(api_url or DEFAULT_API_URL).strip()
    if "://" not in value:
        value = "http://" + value
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError(f"无效的 ixBrowser Local API 地址: {api_url}")
    if parsed.path.rstrip("/") not in {"", "/api/v2"}:
        raise ValueError("ixBrowser API 地址只支持主机、端口及可选的 /api/v2 路径")
    return parsed.hostname, parsed.port or 53200


def _profile_rows(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "list", "rows", "items"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _profile_id(profile):
    if not isinstance(profile, dict):
        return ""
    return str(profile.get("profile_id") or profile.get("id") or "").strip()


def _sdk_profile_id(profile_id):
    if isinstance(profile_id, int) and not isinstance(profile_id, bool):
        return profile_id
    value = str(profile_id or "").strip()
    if not value.isdigit():
        raise ValueError(f"无效的 ixBrowser profile_id: {profile_id!r}")
    return int(value)


class IXBrowserClient:
    """Expose the subset of ixBrowser operations used by this repository."""

    def __init__(self, api_url=DEFAULT_API_URL, sdk_client=None):
        if sdk_client is None:
            if SDKClient is None:
                raise RuntimeError(
                    "ixBrowser provider requires ixbrowser-local-api>=1.2.6,<2"
                )
            host, port = _api_target(api_url)
            sdk_client = SDKClient(target=host, port=port)
        self.sdk = sdk_client

    def _required(self, result, action):
        if result is not None:
            return result
        code = getattr(self.sdk, "code", None)
        message = getattr(self.sdk, "message", None) or "未知错误"
        suffix = f"（错误码 {code}）" if code is not None else ""
        raise RuntimeError(f"ixBrowser {action}失败: {message}{suffix}")

    @staticmethod
    def _normalize(profile):
        item = dict(profile)
        item["id"] = _profile_id(item)
        return item

    def list_browsers(self, name=None, page_size=100):
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        profiles = []
        page = 1
        while True:
            result = self._required(
                self.sdk.get_profile_list(keyword=name, page=page, limit=page_size),
                "读取窗口列表",
            )
            rows = _profile_rows(result)
            profiles.extend(self._normalize(row) for row in rows if isinstance(row, dict))
            total = getattr(self.sdk, "total", None)
            if not rows or len(rows) < page_size:
                break
            if total is not None and len(profiles) >= int(total):
                break
            page += 1
        return profiles

    def open_browser(self, profile_id):
        result = self._required(
            self.sdk.open_profile(
                _sdk_profile_id(profile_id),
                cookies_backup=True,
                load_profile_info_page=False,
            ),
            "打开窗口",
        )
        if not isinstance(result, dict):
            raise RuntimeError("ixBrowser 打开窗口后未返回调试地址")
        endpoint = result.get("debugging_address") or result.get("debuggingAddress")
        if not endpoint:
            raise RuntimeError("ixBrowser 打开窗口后未返回 debugging_address")
        endpoint = str(endpoint).strip()
        if not endpoint.startswith(("http://", "https://", "ws://", "wss://")):
            endpoint = "http://" + endpoint
        return endpoint

    def close_browser(self, profile_id):
        result = self.sdk.close_profile(_sdk_profile_id(profile_id))
        if result is None:
            code = getattr(self.sdk, "code", None)
            message = getattr(self.sdk, "message", None) or "未知错误"
            suffix = f"（错误码 {code}）" if code is not None else ""
            print(f"[warn] ixBrowser 关闭窗口失败: {message}{suffix}")
            return False
        return True

    def is_open(self, profile_id):
        wanted = str(profile_id)
        for method_name in ("get_opened_profile_list", "get_native_opened_profile_list"):
            method = getattr(self.sdk, method_name, None)
            if method is None:
                continue
            result = method()
            if result is None:
                continue
            if any(_profile_id(row) == wanted for row in _profile_rows(result)):
                return True
        return False

    def create_browser(
        self,
        name,
        proxy_type=None,
        host=None,
        port=None,
        username="",
        password="",
        group_id=None,
    ):
        if Profile is None or Preference is None or Proxy is None:
            raise RuntimeError(
                "ixBrowser provider requires ixbrowser-local-api>=1.2.6,<2"
            )

        profile = Profile()
        profile.name = name
        profile.set_custom_page("https://www.tiktok.com/")
        profile.random_color()
        if group_id not in (None, ""):
            profile.group_id = int(group_id) if str(group_id).isdigit() else group_id

        if proxy_type is not None:
            if not host or port in (None, ""):
                raise ValueError("设置代理时必须提供 host 和 port")
            proxy = Proxy()
            proxy.change_to_custom_mode(
                proxy_type=proxy_type,
                proxy_ip=host,
                proxy_port=str(port),
                proxy_user=username or None,
                proxy_password=password or None,
            )
            profile.proxy_config = proxy
        elif any(
            value not in (None, "") for value in (host, port, username, password)
        ):
            raise ValueError("未指定代理类型时不能提供代理连接信息")

        preference = Preference()
        preference.set_cloud_backup(
            save_cookies=1,
            save_indexed_db=1,
            save_local_storage=1,
        )
        preference.load_profile_info_page = 0
        profile.preference_config = preference

        result = self._required(self.sdk.create_profile(profile), "创建窗口")
        if isinstance(result, dict):
            profile_id = (
                result.get("profile_id")
                or result.get("new_profile_id")
                or result.get("id")
            )
        else:
            profile_id = result
        if profile_id in (None, "", True, False):
            raise RuntimeError("ixBrowser 已创建窗口，但没有返回 profile_id")
        return str(profile_id)
