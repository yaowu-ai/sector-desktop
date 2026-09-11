from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import bitbrowser  # noqa: E402
import browser_providers as providers  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_environment_mapping() -> None:
    original_show = os.environ.get("AM_SHOW_BROWSER_WINDOW")
    original_task = os.environ.get("AM_TASK_TYPE")
    try:
        os.environ.pop("AM_SHOW_BROWSER_WINDOW", None)
        os.environ["AM_TASK_TYPE"] = "fyp"
        require(providers.show_browser_window_enabled(), "missing setting should keep browser visible")
        require(not providers.background_browser_enabled(), "visible setting should not add background args")

        os.environ["AM_SHOW_BROWSER_WINDOW"] = "0"
        require(providers.background_browser_enabled(), "disabled setting should enable background mode")
        require(
            providers.browser_launch_args() == ["--start-minimized"],
            "background mode should use the minimized Chromium argument",
        )

        os.environ["AM_TASK_TYPE"] = "tiktok_register"
        require(
            not providers.background_browser_enabled(),
            "interactive registration should remain visible",
        )
    finally:
        if original_show is None:
            os.environ.pop("AM_SHOW_BROWSER_WINDOW", None)
        else:
            os.environ["AM_SHOW_BROWSER_WINDOW"] = original_show
        if original_task is None:
            os.environ.pop("AM_TASK_TYPE", None)
        else:
            os.environ["AM_TASK_TYPE"] = original_task


def test_bitbrowser_open_forwards_optional_args() -> None:
    captured = {}
    original_post = bitbrowser.requests.post

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "data": {"http": "127.0.0.1:45123"}}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    bitbrowser.requests.post = fake_post
    try:
        endpoint = bitbrowser.BitBrowserClient().open_browser(
            "profile-1",
            args=["--start-minimized"],
        )
        require(endpoint == "http://127.0.0.1:45123", "BitBrowser endpoint normalization changed")
        require(
            captured["kwargs"]["json"] == {
                "id": "profile-1",
                "args": ["--start-minimized"],
            },
            "BitBrowser launch args were not forwarded",
        )
    finally:
        bitbrowser.requests.post = original_post


def test_bitbrowser_background_mode_falls_back_to_visible() -> None:
    original_client = providers.BitBrowserClient
    original_show = os.environ.get("AM_SHOW_BROWSER_WINDOW")
    original_task = os.environ.get("AM_TASK_TYPE")
    calls = []

    class FakeClient:
        def __init__(self, _api_url):
            pass

        def is_open(self, _profile_id):
            return False

        def open_browser(self, _profile_id, *, args=None):
            calls.append(args)
            if args:
                raise ValueError("launch args unsupported")
            return "http://127.0.0.1:45123"

        def browser_pid(self, _profile_id):
            return None

    providers.BitBrowserClient = FakeClient
    os.environ["AM_SHOW_BROWSER_WINDOW"] = "0"
    os.environ["AM_TASK_TYPE"] = "fyp"
    try:
        session = providers.BitBrowserProvider().start_session(
            {"id": "account-1", "browser": {"profile_id": "profile-1"}},
            {"bitbrowser": {"api_url": "http://127.0.0.1:54345"}},
        )
        require(
            calls == [["--start-minimized"], None],
            "unsupported background args should retry with a visible launch",
        )
        require(
            session.cdp_endpoint == "http://127.0.0.1:45123",
            "visible fallback should preserve the CDP endpoint",
        )
    finally:
        providers.BitBrowserClient = original_client
        if original_show is None:
            os.environ.pop("AM_SHOW_BROWSER_WINDOW", None)
        else:
            os.environ["AM_SHOW_BROWSER_WINDOW"] = original_show
        if original_task is None:
            os.environ.pop("AM_TASK_TYPE", None)
        else:
            os.environ["AM_TASK_TYPE"] = original_task


if __name__ == "__main__":
    test_environment_mapping()
    test_bitbrowser_open_forwards_optional_args()
    test_bitbrowser_background_mode_falls_back_to_visible()
    print("browser window mode checks ok")
