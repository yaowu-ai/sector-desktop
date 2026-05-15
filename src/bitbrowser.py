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
