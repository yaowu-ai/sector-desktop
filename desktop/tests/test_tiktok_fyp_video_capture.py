import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core import runtime
from platforms.tiktok import actions as tiktok_actions
from platforms.tiktok.fyp import build_fyp_plan


class FakeMouse:
    def move(self, *args, **kwargs):
        pass

    def wheel(self, *args, **kwargs):
        pass


class FakeKeyboard:
    def press(self, *args, **kwargs):
        pass


class FakePage:
    viewport_size = {"width": 1280, "height": 800}

    def __init__(self):
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()
        self.goto_urls = []

    def goto(self, url, timeout=0):
        self.goto_urls.append((url, timeout))


class TikTokFypVideoCaptureTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        runtime.initialize_db_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_build_fyp_plan_includes_default_video_capture_config(self):
        plan = build_fyp_plan(
            {"id": "acct_1", "platform": "tiktok"},
            {
                "platforms": {
                    "tiktok": {
                        "warmup": {
                            "fyp_browse_minutes": [1, 1],
                            "like_probability": 0,
                            "follows_per_session": [0, 0],
                            "comment": {"enabled": False},
                        }
                    }
                }
            },
        )

        self.assertEqual(
            plan["video_capture"],
            {
                "enabled": True,
                "max_title_length": 300,
                "max_description_length": 600,
                "capture_timeout_ms": 800,
            },
        )

    def test_build_fyp_plan_reads_video_capture_overrides(self):
        plan = build_fyp_plan(
            {"id": "acct_1", "platform": "tiktok"},
            {
                "platforms": {
                    "tiktok": {
                        "warmup": {
                            "fyp_browse_minutes": [1, 1],
                            "like_probability": 0,
                            "follows_per_session": [0, 0],
                            "comment": {"enabled": False},
                            "video_capture": {
                                "enabled": False,
                                "max_title_length": 120,
                                "max_description_length": 240,
                                "capture_timeout_ms": 500,
                            },
                        }
                    }
                }
            },
        )

        self.assertEqual(
            plan["video_capture"],
            {
                "enabled": False,
                "max_title_length": 120,
                "max_description_length": 240,
                "capture_timeout_ms": 500,
            },
        )

    def test_build_fyp_plan_allows_ai_comment_target_without_comment_pool(self):
        config = {
            "ai_comment": {"enabled": True},
            "platforms": {
                "tiktok": {
                    "warmup": {
                        "fyp_browse_minutes": [1, 1],
                        "like_probability": 0,
                        "follows_per_session": [0, 0],
                        "comment": {
                            "enabled": True,
                            "comments_per_session": [1, 1],
                        },
                    }
                }
            },
        }

        with patch("platforms.tiktok.fyp.load_comments", return_value=[]):
            plan = build_fyp_plan({"id": "acct_1", "platform": "tiktok"}, config)

        self.assertEqual(plan["comments_pool"], [])
        self.assertEqual(plan["comments_target"], 1)
        self.assertTrue(plan["ai_comment"]["enabled"])

    def test_build_fyp_plan_keeps_comment_disabled_as_total_comment_gate(self):
        config = {
            "ai_comment": {"enabled": True},
            "platforms": {
                "tiktok": {
                    "warmup": {
                        "fyp_browse_minutes": [1, 1],
                        "like_probability": 0,
                        "follows_per_session": [0, 0],
                        "comment": {
                            "enabled": False,
                            "comments_per_session": [1, 1],
                        },
                    }
                }
            },
        }

        plan = build_fyp_plan({"id": "acct_1", "platform": "tiktok"}, config)

        self.assertEqual(plan["comments_target"], 0)
        self.assertEqual(plan["comment_skip_detail"], "评论开关关闭（comment.enabled=false）")

    def test_fyp_browse_records_video_info_and_updates_like_result(self):
        page = FakePage()
        captured = {
            "video_id": "7390000000000000003",
            "video_url": "https://www.tiktok.com/@creator/video/7390000000000000003",
            "author_handle": "creator",
            "title": "Captured video",
            "description": "Captured video",
            "capture_status": "ok",
            "raw_source": "dom_caption",
        }

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", side_effect=[0, 1]),
            patch.object(tiktok_actions.uuid, "uuid4", return_value=FakeUuid("session_1")),
            patch.object(tiktok_actions, "capture_active_video_info", return_value=captured) as capture,
            patch.object(tiktok_actions, "try_like_with_detail", return_value=(True, "liked")),
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=1,
                follows_target=0,
                comments_target=0,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=True,
            )

        self.assertEqual(result["videos"], 1)
        self.assertEqual(result["likes"], 1)
        self.assertEqual(result["video_capture"]["records"], 1)
        self.assertEqual(result["video_capture"]["failures"], 0)
        capture.assert_called_once()

        row = self.conn.execute(
            "SELECT session_id, video_index, video_id, title, watch_seconds, liked "
            "FROM fyp_video_views WHERE account_id='acct_1'"
        ).fetchone()
        self.assertEqual(row, ("session_1", 1, "7390000000000000003", "Captured video", 4.0, 1))

    def test_fyp_browse_skips_capture_when_disabled(self):
        page = FakePage()

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", return_value=1),
            patch.object(tiktok_actions, "capture_active_video_info") as capture,
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=0,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=False,
            )

        self.assertEqual(result["videos"], 1)
        self.assertFalse(result["video_capture"]["enabled"])
        capture.assert_not_called()
        count = self.conn.execute("SELECT COUNT(*) FROM fyp_video_views").fetchone()[0]
        self.assertEqual(count, 0)

    def test_fyp_browse_continues_when_capture_raises(self):
        page = FakePage()

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", return_value=1),
            patch.object(tiktok_actions.uuid, "uuid4", return_value=FakeUuid("session_failed")),
            patch.object(tiktok_actions, "capture_active_video_info", side_effect=RuntimeError("dom changed")),
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=0,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=True,
            )

        self.assertEqual(result["videos"], 1)
        self.assertEqual(result["video_capture"]["records"], 1)
        self.assertEqual(result["video_capture"]["failures"], 1)
        row = self.conn.execute(
            "SELECT capture_status, capture_error FROM fyp_video_views WHERE account_id='acct_1'"
        ).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertIn("dom changed", row[1])

    def test_fyp_browse_uses_pool_when_ai_comment_disabled(self):
        page = FakePage()

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", side_effect=[1, 0]),
            patch.object(tiktok_actions.random, "choice", return_value="pool text") as choice,
            patch.object(tiktok_actions, "generate_ai_comment") as generate,
            patch.object(tiktok_actions, "try_comment", return_value=True) as try_comment,
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=1,
                comments_pool=["pool text"],
                comment_prob=1,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=False,
                ai_comment_config={"enabled": False},
            )

        self.assertEqual(result["comments"], 1)
        choice.assert_called_once()
        generate.assert_not_called()
        try_comment.assert_called_once()
        self.assertEqual(try_comment.call_args.args[2], "pool text")
        comment_ai_logs = self.conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE action='comment_ai'"
        ).fetchone()[0]
        self.assertEqual(comment_ai_logs, 0)

    def test_fyp_browse_uses_ai_comment_when_generation_succeeds(self):
        page = FakePage()
        captured = {
            "title": "Captured video",
            "description": "Useful demo",
            "capture_status": "ok",
            "raw_source": "dom_caption",
        }

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", side_effect=[1, 0]),
            patch.object(tiktok_actions.random, "choice") as choice,
            patch.object(tiktok_actions.uuid, "uuid4", return_value=FakeUuid("session_ai")),
            patch.object(tiktok_actions, "capture_active_video_info", return_value=captured),
            patch.object(
                tiktok_actions,
                "generate_ai_comment",
                return_value={
                    "ok": True,
                    "comment": "AI text",
                    "source": "ai",
                    "reason": "generated",
                    "latency_ms": 12,
                },
            ) as generate,
            patch.object(tiktok_actions, "try_comment", return_value=True) as try_comment,
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=1,
                comments_pool=["pool text"],
                comment_prob=1,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=True,
                ai_comment_config={"enabled": True, "provider": "kimi_moonshot"},
            )

        self.assertEqual(result["comments"], 1)
        choice.assert_not_called()
        generate.assert_called_once()
        try_comment.assert_called_once()
        self.assertEqual(try_comment.call_args.args[2], "AI text")
        row = self.conn.execute(
            "SELECT status, detail FROM action_log WHERE action='comment_ai'"
        ).fetchone()
        self.assertEqual(row[0], "ok")
        self.assertIn("comment_source=ai", row[1])
        self.assertIn("latency_ms=12", row[1])

    def test_fyp_browse_falls_back_to_pool_when_ai_fails(self):
        page = FakePage()

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", side_effect=[1, 0]),
            patch.object(tiktok_actions.random, "choice", return_value="pool text"),
            patch.object(tiktok_actions.uuid, "uuid4", return_value=FakeUuid("session_fallback")),
            patch.object(
                tiktok_actions,
                "capture_active_video_info",
                return_value={"title": "Captured video", "description": "Useful demo"},
            ),
            patch.object(
                tiktok_actions,
                "generate_ai_comment",
                return_value={
                    "ok": False,
                    "comment": "",
                    "source": "ai",
                    "reason": "timeout",
                    "error": "api_key=secret timed out",
                },
            ),
            patch.object(tiktok_actions, "try_comment", return_value=True) as try_comment,
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=1,
                comments_pool=["pool text"],
                comment_prob=1,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=True,
                ai_comment_config={"enabled": True, "provider": "kimi_moonshot"},
            )

        self.assertEqual(result["comments"], 1)
        self.assertEqual(try_comment.call_args.args[2], "pool text")
        row = self.conn.execute(
            "SELECT status, detail FROM action_log WHERE action='comment_ai'"
        ).fetchone()
        self.assertEqual(row[0], "fail")
        self.assertIn("comment_source=pool", row[1])
        self.assertIn("reason=timeout", row[1])
        self.assertIn("fallback=pool", row[1])
        self.assertNotIn("secret", row[1])

    def test_choose_comment_text_falls_back_for_validation_failures_with_custom_provider(self):
        for reason in ("url", "mention", "multi_line", "too_long"):
            with self.subTest(reason=reason):
                with (
                    patch.object(tiktok_actions.random, "choice", return_value="pool text"),
                    patch.object(
                        tiktok_actions,
                        "generate_ai_comment",
                        return_value={
                            "ok": False,
                            "comment": "",
                            "source": "ai",
                            "reason": reason,
                        },
                    ) as generate,
                ):
                    text, event = tiktok_actions.choose_comment_text(
                        ["pool text"],
                        {"title": "Captured video", "description": "Useful demo"},
                        {"enabled": True, "provider": "openai_compatible_custom"},
                    )

                self.assertEqual(text, "pool text")
                self.assertEqual(event["status"], "fail")
                self.assertIn("comment_source=pool", event["detail"])
                self.assertIn(f"reason={reason}", event["detail"])
                self.assertIn("fallback=pool", event["detail"])
                self.assertEqual(
                    generate.call_args.args[1]["provider"],
                    "openai_compatible_custom",
                )

    def test_fyp_browse_does_not_crash_when_ai_fails_and_pool_empty(self):
        page = FakePage()

        with (
            patch.object(tiktok_actions, "human_pause"),
            patch.object(tiktok_actions, "_scroll_to_next_video"),
            patch.object(tiktok_actions.time, "time", side_effect=[0, 0, 999]),
            patch.object(tiktok_actions.time, "sleep"),
            patch.object(tiktok_actions.random, "choices", return_value=[4]),
            patch.object(tiktok_actions.random, "random", side_effect=[1, 0]),
            patch.object(tiktok_actions.uuid, "uuid4", return_value=FakeUuid("session_empty")),
            patch.object(
                tiktok_actions,
                "capture_active_video_info",
                return_value={"title": "Captured video", "description": "Useful demo"},
            ),
            patch.object(
                tiktok_actions,
                "generate_ai_comment",
                return_value={
                    "ok": False,
                    "comment": "",
                    "source": "ai",
                    "reason": "missing_api_key",
                },
            ),
            patch.object(tiktok_actions, "try_comment") as try_comment,
        ):
            result = tiktok_actions.fyp_browse(
                page,
                duration_minutes=0.001,
                like_prob=0,
                follows_target=0,
                comments_target=1,
                comments_pool=[],
                comment_prob=1,
                conn=self.conn,
                platform="tiktok",
                account_id="acct_1",
                capture_video_info=True,
                ai_comment_config={"enabled": True, "provider": "kimi_moonshot"},
            )

        self.assertEqual(result["comments"], 0)
        self.assertEqual(result["comment_attempts"], 1)
        self.assertEqual(result["comment_failures"], 1)
        try_comment.assert_not_called()
        row = self.conn.execute(
            "SELECT status, detail FROM action_log WHERE action='comment_ai'"
        ).fetchone()
        self.assertEqual(row[0], "fail")
        self.assertIn("comment_source=none", row[1])
        self.assertIn("fallback=none", row[1])


class FakeUuid:
    def __init__(self, value):
        self.hex = value


if __name__ == "__main__":
    unittest.main()
