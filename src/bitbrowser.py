"""BitBrowser local API client."""
import requests


class BitBrowserClient:
    def __init__(self, api_url="http://127.0.0.1:54345"):
        self.api_url = api_url.rstrip("/")

    def open_browser(self, profile_id, timeout=90):
        resp = requests.post(
            f"{self.api_url}/browser/open",
            json={"id": profile_id},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"BitBrowser open failed: {data}")

        d = data["data"]
        # Prefer ws (direct websocket URL); fall back to http endpoint.
        cdp = d.get("ws") or d.get("webSocketDebuggerUrl") \
            or d.get("http") or d.get("debuggerAddress")
        if not cdp:
            raise RuntimeError(f"No CDP endpoint in BitBrowser response: {data}")

        # BitBrowser sometimes returns "127.0.0.1:port" without scheme — add it.
        if not cdp.startswith(("http://", "https://", "ws://", "wss://")):
            cdp = f"http://{cdp}"
        return cdp

    def check_proxy(self, proxy_type, host, port, username="", password="",
                    check_exists=True, timeout=30):
        """Check proxy connectivity through BitBrowser's Local API."""
        resp = requests.post(
            f"{self.api_url}/checkagent",
            json={
                "proxyType": proxy_type,
                "host": host,
                "port": str(port),
                "proxyUserName": username,
                "proxyPassword": password,
                "checkExists": int(check_exists),
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            message = data.get("msg") or data.get("message") or "unknown error"
            raise RuntimeError(f"BitBrowser proxy check failed: {message}")

        check_result = data.get("data")
        # /checkagent wraps its own success result inside the normal API result.
        if isinstance(check_result, dict) and "success" in check_result:
            if not check_result.get("success"):
                message = (check_result.get("msg") or
                           check_result.get("message") or
                           "unknown error")
                raise RuntimeError(f"BitBrowser proxy check failed: {message}")
            check_result = check_result.get("data")
        return check_result

    def list_browsers(self, name=None, page_size=100, timeout=30):
        """Return all browser profiles, following /browser/list pagination."""
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        profiles = []
        page = 0
        while True:
            payload = {"page": page, "pageSize": page_size, "sort": "asc"}
            if name:
                payload["name"] = name
            resp = requests.post(
                f"{self.api_url}/browser/list",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            if not result.get("success"):
                message = result.get("msg") or result.get("message") or "unknown error"
                raise RuntimeError(f"BitBrowser list failed: {message}")

            data = result.get("data")
            total = None
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = None
                for key in ("list", "rows", "records", "items"):
                    if isinstance(data.get(key), list):
                        items = data[key]
                        break
                if items is None:
                    raise RuntimeError(
                        "BitBrowser list returned an unsupported data structure"
                    )
                for key in ("total", "totalNum", "totalCount"):
                    if data.get(key) is not None:
                        total = int(data[key])
                        break
            else:
                raise RuntimeError(
                    "BitBrowser list returned an unsupported data structure"
                )

            profiles.extend(items)
            if not items or len(items) < page_size:
                break
            if total is not None and len(profiles) >= total:
                break
            page += 1
        return profiles

    def create_browser(self, name, proxy_type, host, port, username="", password="",
                       group_id=None, timeout=30):
        """Create a TikTok browser profile with a fixed custom proxy."""
        payload = {
            "name": name,
            "platform": "https://www.tiktok.com",
            "platformIcon": "tiktok.com",
            "url": "https://www.tiktok.com/foryou",
            "proxyMethod": 2,
            "proxyType": proxy_type,
            "host": host,
            "port": int(port),
            "proxyUserName": username,
            "proxyPassword": password,
            "ipCheckService": "ip-api",
            "browserFingerPrint": {},
            "stopWhileNetError": True,
            "randomFingerprint": False,
            "workbench": "disable",
        }
        if group_id:
            payload["groupId"] = group_id

        resp = requests.post(
            f"{self.api_url}/browser/update",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise RuntimeError(
                "BitBrowser create failed: "
                f"{result.get('msg') or result.get('message') or 'unknown error'}"
            )

        data = result.get("data")
        if isinstance(data, dict):
            profile_id = data.get("id")
        elif isinstance(data, str):
            profile_id = data
        else:
            profile_id = None
        if not profile_id:
            raise RuntimeError(
                "BitBrowser created the profile but returned no profile id"
            )
        return profile_id

    def close_browser(self, profile_id):
        try:
            requests.post(
                f"{self.api_url}/browser/close",
                json={"id": profile_id},
                timeout=10,
            )
        except Exception as e:
            print(f"[warn] close failed: {e}")

    def is_open(self, profile_id):
        try:
            resp = requests.post(
                f"{self.api_url}/browser/pids",
                json={"ids": [profile_id]},
                timeout=5,
            )
            return bool(resp.json().get("data", {}).get(profile_id))
        except Exception:
            return False
