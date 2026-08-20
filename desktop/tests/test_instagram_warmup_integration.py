import os
import shutil
import sqlite3
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core import runtime
from platforms.instagram_runner import bridge
from platforms.instagram_runner import runner as instagram_runner


class FakeProvider:
    name = "bitbrowser"

    def __init__(self):
        self.validated = False

    def validate_account(self, _account, _config):
        self.validated = True


class FakeBrowserSession:
    def __init__(self, stats):
        self.stats = stats
        self.calls = []

    def run_one_profile(self, profile_id, bitbrowser, conn, args, *, account_id=None):
        self.calls.append(
            {
                "profile_id": profile_id,
                "bitbrowser": bitbrowser,
                "conn": conn,
                "args": args,
                "account_id": account_id,
            }
        )
        return dict(self.stats)


class FakeBitBrowser:
    def __init__(self, proxy_method=1):
        self.proxy_method = proxy_method
        self.opened = False

    def list_browsers(self, name):
        return [{"id": "resolved-profile", "name": name}]

    def is_open(self, _profile_id):
        return False

    def get_browser_info(self, _profile_id):
        return {"proxyMethod": self.proxy_method}

    def open_browser(self, _profile_id):
        self.opened = True
        raise AssertionError("no-proxy preflight should stop before opening BitBrowser")

    def close_browser(self, _profile_id):
        return None


class InstagramWarmupIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parent / "tmp-instagram-warmup"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = temp_root / f"run-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.config_path = self.temp_dir / "accounts.yaml"
        self.config_path.write_text("accounts: []\n", encoding="utf-8")
        (self.temp_dir / "comments.txt").write_text(
            "# shared pool\nGreat post\nUseful idea\n",
            encoding="utf-8",
        )
        os.environ["AM_DATA_DIR"] = str(self.temp_dir / "data")
        runtime.configure_runtime(self.config_path)
        bridge.load_ins_modules.cache_clear()
        self.conn = sqlite3.connect(":memory:")
        runtime.initialize_db_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        os.environ.pop("AM_DATA_DIR", None)
        bridge.load_ins_modules.cache_clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_instagram_args_reads_platform_warmup_config(self):
        config = {
            "bitbrowser": {"api_url": "http://127.0.0.1:54346"},
            "defaults": {"daily_actions": {"like_probability": 0.9}},
            "platforms": {
                "instagram": {
                    "warmup": {
                        "duration": "21",
                        "like_prob": "0.25",
                        "save_prob": 0.05,
                        "comment_prob": "0.2",
                        "max_likes_per_day": "9",
                        "max_comments_per_session": "2",
                        "require_proxy": "false",
                    }
                }
            },
        }

        args = bridge.build_instagram_args(
            {"id": "acct_1", "bitbrowser_profile_id": "profile_1"},
            config,
        )

        self.assertEqual(args.profiles, "acct_1")
        self.assertEqual(args.api_url, "http://127.0.0.1:54346")
        self.assertEqual(args.config, runtime.CONFIG_PATH)
        self.assertEqual(args.duration, 21)
        self.assertEqual(args.max_likes_per_day, 9)
        self.assertEqual(args.max_comments_per_session, 2)
        self.assertEqual(args.like_prob, 0.25)
        self.assertEqual(args.save_prob, 0.05)
        self.assertEqual(args.comment_prob, 0.2)
        self.assertFalse(args.require_proxy)

    def test_instagram_comments_reuse_shared_comment_pool_by_default(self):
        comments = runtime.load_comments({"platforms": {"instagram": {}}}, "instagram")

        self.assertEqual(comments, ["Great post", "Useful idea"])

    def test_runtime_cooldown_and_budget_survive_reopen(self):
        db_uri = f"file:ins_runtime_{uuid.uuid4().hex}?mode=memory&cache=shared"
        conn = sqlite3.connect(db_uri, uri=True)
        runtime.initialize_db_schema(conn)
        try:
            runtime.log_ins_action(conn, "session_1", "like", "ok", "liked", "profile_1")
            runtime.log_ins_action(conn, "session_1", "comment", "ok", "Nice", "profile_1")
            runtime.set_ins_cooldown(conn, "profile_1", 2, "challenge")

            reopened = sqlite3.connect(db_uri, uri=True)
            args = types.SimpleNamespace(
                max_likes_per_day=2,
                max_saves_per_day=0,
                max_follows_per_day=0,
                max_comments_per_day=1,
            )
            remaining = runtime.compute_ins_remaining_budget(reopened, "profile_1", args)
            cooldown = runtime.get_ins_cooldown_until(reopened, "profile_1")
        finally:
            conn.close()
            if "reopened" in locals():
                reopened.close()

        self.assertEqual(remaining["like"], 1)
        self.assertEqual(remaining["comment"], 0)
        self.assertIsNone(remaining["save"])
        self.assertIsNotNone(cooldown)

    def test_run_session_uses_instagram_execution_branch(self):
        provider = FakeProvider()
        fake_browser_session = FakeBrowserSession(
            {"reels": 3, "stories": 1, "explore": 2, "likes": 4, "follows": 1, "comments": 2}
        )
        fake_client = object()
        config = {
            "bitbrowser": {"api_url": "http://127.0.0.1:54346"},
            "platforms": {"instagram": {"warmup": {"duration": 12}}},
        }
        account = {"id": "acct_1", "bitbrowser_profile_id": "profile_1"}

        with patch.object(instagram_runner, "provider_for_account", return_value=provider), patch.object(
            instagram_runner,
            "load_ins_modules",
            return_value=types.SimpleNamespace(browser_session=fake_browser_session),
        ), patch.object(instagram_runner, "create_bitbrowser_client", return_value=fake_client):
            summary = instagram_runner.run_session(account, config, self.conn)

        self.assertTrue(provider.validated)
        self.assertEqual(summary["platform"], "instagram")
        self.assertEqual(summary["task_type"], "instagram_warmup")
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["videos"], 6)
        self.assertEqual(summary["likes"], 4)
        self.assertEqual(summary["comments"], 2)
        self.assertEqual(fake_browser_session.calls[0]["profile_id"], "profile_1")
        self.assertEqual(fake_browser_session.calls[0]["bitbrowser"], fake_client)
        self.assertEqual(fake_browser_session.calls[0]["account_id"], "acct_1")

    def test_run_session_reports_risk_block_as_skip(self):
        provider = FakeProvider()
        fake_browser_session = FakeBrowserSession(
            {"_blocked": 1, "_block_detail": "challenge_checkpoint", "errors": 0}
        )
        account = {"id": "acct_1", "bitbrowser_profile_id": "profile_1"}

        with patch.object(instagram_runner, "provider_for_account", return_value=provider), patch.object(
            instagram_runner,
            "load_ins_modules",
            return_value=types.SimpleNamespace(browser_session=fake_browser_session),
        ), patch.object(instagram_runner, "create_bitbrowser_client", return_value=object()):
            summary = instagram_runner.run_session(account, {"platforms": {"instagram": {}}}, self.conn)

        self.assertEqual(summary["status"], "skip")
        self.assertEqual(summary["error"], "challenge_checkpoint")

    def test_run_session_rejects_non_bitbrowser_provider(self):
        provider = FakeProvider()
        provider.name = "builtin_chromium"

        with patch.object(instagram_runner, "provider_for_account", return_value=provider):
            with self.assertRaisesRegex(ValueError, "requires the BitBrowser provider"):
                instagram_runner.run_session({"id": "acct_1"}, {}, self.conn)

    def test_require_proxy_rejects_profile_without_proxy_before_opening_browser(self):
        modules = bridge.load_ins_modules()
        args = bridge.build_instagram_args(
            {"id": "acct_1", "bitbrowser_profile_id": "proxy-profile"},
            {"platforms": {"instagram": {"warmup": {"duration": 1, "require_proxy": True}}}},
        )
        fake_bitbrowser = FakeBitBrowser(proxy_method=1)

        with patch.object(modules.storage, "session_log", return_value=None), patch.object(
            modules.status, "update", return_value=None
        ), patch.object(
            modules.status, "mark_error", return_value=None
        ), patch.object(modules.status, "mark_done", return_value=None), patch.object(
            modules.status, "mark_blocked", return_value=None
        ):
            stats = modules.browser_session.run_one_profile(
                "proxy-profile",
                fake_bitbrowser,
                self.conn,
                args,
                account_id="acct_1",
            )

        self.assertFalse(fake_bitbrowser.opened)
        self.assertEqual(stats["errors"], 1)
        rows = self.conn.execute(
            "SELECT action, status, detail, profile_id FROM ins_warm_log ORDER BY id"
        ).fetchall()
        self.assertIn(("proxy_check", "warn", "profile proxy-profile 未检测到绑定代理", "acct_1"), rows)
        self.assertIn(("session", "error", "no_proxy_bound", "acct_1"), rows)


if __name__ == "__main__":
    unittest.main()
