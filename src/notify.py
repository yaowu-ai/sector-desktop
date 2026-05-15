"""Notification module — Server酱 / Bark / generic webhook."""
import requests


def send(notify_config, title, content):
    """Send a notification. No-op if disabled or misconfigured."""
    if not notify_config or not notify_config.get("enabled"):
        return False

    ntype = notify_config.get("type", "").lower()
    try:
        if ntype == "serverchan":
            key = notify_config.get("serverchan", {}).get("sendkey", "")
            if not key:
                print("[warn] serverchan sendkey not set")
                return False
            url = f"https://sctapi.ftqq.com/{key}.send"
            resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
            return resp.ok

        if ntype == "bark":
            base = notify_config.get("bark", {}).get("url", "").rstrip("/")
            if not base:
                print("[warn] bark url not set")
                return False
            resp = requests.post(
                f"{base}/{title}",
                json={"body": content, "group": "tiktok-bot"},
                timeout=10,
            )
            return resp.ok

        if ntype == "webhook":
            url = notify_config.get("webhook", {}).get("url", "")
            if not url:
                print("[warn] webhook url not set")
                return False
            resp = requests.post(url, json={"title": title, "content": content}, timeout=10)
            return resp.ok

        print(f"[warn] unknown notify type: {ntype}")
        return False
    except Exception as e:
        print(f"[warn] notify failed: {e}")
        return False
