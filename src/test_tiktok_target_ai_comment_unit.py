import sqlite3
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from core import runtime
from platforms.tiktok import actions, engagement, target


class TargetAiCommentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.conn = sqlite3.connect(":memory:")
        runtime.initialize_db_schema(self.conn)
        self.addCleanup(self.conn.close)
        self.page = MagicMock()
        self.page.url = "https://www.tiktok.com/@brand/video/101"
        self.config = {
            "ai_comment": {"enabled": True, "timeout_seconds": 3, "model": "test-model"},
            "target_accounts": {
                "enabled": True, "participants": ["acc"], "handles": ["brand"],
                "like_probability": 0, "comment_probability": 1,
            },
        }
        for module, name in ((target, "human_pause"), (target, "session_log"),
                             (engagement, "human_pause"), (engagement.time, "sleep")):
            self.stack.enter_context(patch.object(module, name))
        self.stack.enter_context(patch.object(target, "navigate_target_page", return_value=(True, "ok")))
        self.stack.enter_context(patch.object(target, "fetch_recent_videos", return_value=["101"]))
        self.stack.enter_context(patch.object(engagement, "_open_target_video", return_value=(True, "ok")))
        self.pool = self.stack.enter_context(patch.object(target, "load_comment_file", return_value=["Brand pool comment"]))
        self.capture = self.stack.enter_context(patch.object(
            engagement, "capture_active_video_info", create=True,
            return_value={"title": "A garden video", "description": "Roses in bloom"},
        ))
        self.generate = self.stack.enter_context(patch.object(actions, "generate_ai_comment", return_value={
            "ok": True, "comment": "The roses look lovely", "latency_ms": 12,
        }))
        self.post = self.stack.enter_context(patch.object(engagement, "_comment_on_video_page", return_value=True))

    def run_target(self):
        return target.run_target_engagement(self.page, {"id": "acc"}, self.config, self.conn)

    def source_log(self):
        return self.conn.execute(
            "SELECT status, detail FROM action_log WHERE action='comment_ai'"
        ).fetchall()

    def test_ai_is_preferred_over_brand_pool_and_uses_shared_settings_and_context(self):
        counts = self.run_target()
        self.generate.assert_called_once()
        context, config, _key_reader = self.generate.call_args.args
        self.assertEqual(context, {
            "platform": "tiktok", "title": "A garden video", "description": "Roses in bloom",
        })
        self.assertEqual(config["model"], "test-model")
        self.assertEqual(config["timeout_seconds"], 3)
        self.assertEqual(self.post.call_args.args[2], "The roses look lovely")
        self.assertEqual(counts["comments"], 1)
        self.assertEqual(len(self.source_log()), 1)
        self.assertIn("comment_source=ai", self.source_log()[0][1])

    def test_empty_brand_pool_does_not_disable_ai_comments(self):
        self.pool.return_value = []
        self.assertEqual(self.run_target()["comments"], 1)
        self.generate.assert_called_once()
        self.assertEqual(self.post.call_args.args[2], "The roses look lovely")

    def test_ai_timeout_falls_back_to_brand_pool_without_retry(self):
        self.generate.return_value = {"ok": False, "reason": "timeout"}
        self.assertEqual(self.run_target()["comments"], 1)
        self.generate.assert_called_once()
        self.assertEqual(self.post.call_args.args[2], "Brand pool comment")
        self.assertIn("reason=timeout", self.source_log()[0][1])
        self.assertIn("comment_source=pool", self.source_log()[0][1])

    def test_missing_video_context_uses_pool_without_calling_ai(self):
        self.capture.return_value = {"capture_status": "failed", "title": None, "description": None}
        self.run_target()
        self.generate.assert_not_called()
        self.assertEqual(self.post.call_args.args[2], "Brand pool comment")
        self.assertIn("reason=missing_context", self.source_log()[0][1])

    def test_disabled_ai_preserves_pool_and_does_not_capture_metadata(self):
        self.config["ai_comment"]["enabled"] = False
        self.run_target()
        self.capture.assert_not_called()
        self.generate.assert_not_called()
        self.assertEqual(self.post.call_args.args[2], "Brand pool comment")
        self.assertEqual(self.source_log(), [])

    def test_zero_comment_probability_does_not_capture_generate_or_submit(self):
        self.config["target_accounts"]["comment_probability"] = 0
        self.assertEqual(self.run_target()["comments"], 0)
        self.capture.assert_not_called()
        self.generate.assert_not_called()
        self.post.assert_not_called()

    def test_ai_failure_without_pool_skips_comment(self):
        self.pool.return_value = []
        self.generate.return_value = {"ok": False, "reason": "missing_api_key"}
        self.assertEqual(self.run_target()["comments"], 0)
        self.generate.assert_called_once()
        self.post.assert_not_called()
        self.assertIn("comment_source=none", self.source_log()[0][1])

    def test_unsafe_context_skips_comment_without_pool_fallback_like_fyp(self):
        self.generate.return_value = {"ok": False, "reason": "unsafe_context"}
        self.assertEqual(self.run_target()["comments"], 0)
        self.post.assert_not_called()
        self.assertIn("fallback=none", self.source_log()[0][1])

    def test_video_change_during_generation_prevents_commenting_on_another_video(self):
        def generate(*args):
            self.page.url = "https://www.tiktok.com/@other/video/999"
            return {"ok": True, "comment": "The roses look lovely"}
        self.generate.side_effect = generate
        self.run_target()
        self.generate.assert_called_once()
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
