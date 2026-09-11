import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from auth_adapters import AuthResult, LoginState
from platforms.tiktok import runner


class TikTokRunnerProfileCollectionTests(unittest.TestCase):
    def test_collects_profile_snapshot_before_closing_browser_after_successful_task(self):
        events = []
        summary = self._run_successful_fyp(
            collect_result={
                "account_id": "acc-1",
                "platform": "tiktok",
                "status": "success",
                "handle": "my_account",
                "following": 1,
                "followers": 2,
                "likes": 3,
                "liked": 4,
                "activity": {"comment_publish_evidence": "observed"},
                "error": None,
            },
            events=events,
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["profile_collection_status"], "success")
        self.assertIsNone(summary["profile_collection_error"])
        self.assertEqual(summary["profile_snapshot_id"], 123)
        self.assertIsNone(summary["profile_snapshot_save_error"])
        self.assertEqual(summary["profile_snapshot"]["handle"], "my_account")
        self.assertLess(events.index("collect"), events.index("browser.close"))
        self.assertLess(events.index("save"), events.index("browser.close"))

    def test_profile_collection_failure_does_not_block_browser_close_or_task_success(self):
        events = []
        summary = self._run_successful_fyp(
            collect_result={
                "account_id": "acc-1",
                "platform": "tiktok",
                "status": "failed",
                "error": "RuntimeError: profile timeout",
            },
            events=events,
        )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["profile_collection_status"], "failed")
        self.assertIn("profile timeout", summary["profile_collection_error"])
        self.assertEqual(summary["profile_snapshot_id"], 123)
        self.assertLess(events.index("collect"), events.index("browser.close"))
        self.assertLess(events.index("save"), events.index("browser.close"))

    def _run_successful_fyp(self, collect_result, events):
        account = {"id": "acc-1", "platform": "tiktok"}
        config = {}
        provider = MagicMock(name="provider")
        provider.name = "fake"
        provider.is_open.return_value = False
        provider.start_session.return_value = SimpleNamespace(
            cdp_endpoint="http://127.0.0.1:9222",
            profile_id="profile-1",
        )
        provider.close_session.return_value = SimpleNamespace(status="ok", detail="closed")

        page = MagicMock(name="page")
        page.url = "https://www.tiktok.com/foryou"
        context = MagicMock(name="context")
        context.pages = [page]
        browser = MagicMock(name="browser")
        browser.contexts = [context]
        browser.close.side_effect = lambda: events.append("browser.close")
        playwright = MagicMock(name="playwright")
        playwright.chromium.connect_over_cdp.return_value = browser
        manager = MagicMock(name="manager")

        def collect(browser_arg, account_arg):
            self.assertIs(browser_arg, browser)
            self.assertEqual(account_arg, account)
            events.append("collect")
            return collect_result

        def save(conn_arg, snapshot, task_run_id=None):
            self.assertEqual(snapshot, collect_result)
            self.assertIsNone(task_run_id)
            events.append("save")
            return 123

        with patch.object(runner, "requested_tiktok_task", return_value="fyp"), \
                patch.object(runner, "build_fyp_plan", return_value={
                    "duration": 0.1,
                    "like_prob": 0,
                    "follows_target": 0,
                    "comments_target": 0,
                }), \
                patch.object(runner, "provider_for_account", return_value=provider), \
                patch.object(runner, "bitbrowser_profile_id", return_value="profile-1"), \
                patch.object(runner, "test_cdp_endpoint"), \
                patch.object(runner, "time") as time_module, \
                patch.object(runner, "start_sync_playwright", return_value=(manager, playwright)), \
                patch.object(runner, "background_browser_enabled", return_value=False), \
                patch.object(runner, "auto_close_profile_enabled", return_value=True), \
                patch.object(runner, "ensure_tiktok_authenticated", return_value=AuthResult(
                    platform="tiktok",
                    state=LoginState.LOGGED_IN,
                    detail="ok",
                )), \
                patch.object(runner, "run_tiktok_fyp", return_value={
                    "videos": 1,
                    "likes": 1,
                    "like_failures": 0,
                    "follows": 0,
                    "comments": 0,
                }), \
                patch.object(runner, "collect_profile_snapshot", side_effect=collect), \
                patch.object(runner, "save_profile_snapshot", side_effect=save), \
                patch.object(runner, "session_log"), \
                patch.object(runner, "log_action"), \
                patch.object(runner, "emit_browser_preview"):
            time_module.time.side_effect = [100.0, 160.0]
            time_module.sleep.return_value = None
            return runner.run_session(account, config, MagicMock(name="conn"))


if __name__ == "__main__":
    unittest.main()
