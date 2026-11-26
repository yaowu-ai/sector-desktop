import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from human_mouse import MouseState
from core import runtime
from platforms.tiktok import engagement, target, target_page
from test_tiktok_target_like_persistence_unit import TargetVideoPage


class TimedTargetVideoPage(TargetVideoPage):
    def __init__(self, revert_at_ms=None):
        super().__init__()
        self.elapsed_ms = 0
        self.revert_at_ms = revert_at_ms
        self.waits = []

    def advance(self, milliseconds):
        self.elapsed_ms += milliseconds
        if self.revert_at_ms is not None and self.elapsed_ms >= self.revert_at_ms:
            self.liked = False

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)
        self.advance(milliseconds)


class TargetLikeConfirmationTests(unittest.TestCase):
    def run_video(self, page, comment_prob=0.0):
        with patch.object(engagement, "_open_target_video", return_value=(True, "ok")), \
                patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(engagement.time, "sleep"), \
                patch.object(engagement, "human_pause", side_effect=lambda *a: page.advance(700)), \
                patch.object(engagement, "_comment_on_video_page", return_value=True):
            return engagement.engage_target_video(page, "brand", "101", ["Lovely roses"], 1.0, comment_prob)

    def test_red_heart_that_reverts_before_comments_is_not_reported_as_success(self):
        page = TimedTargetVideoPage(revert_at_ms=1400)
        result = self.run_video(page)
        self.assertFalse(page.liked)
        self.assertFalse(result["liked"])
        self.assertIn("reverted", result["like_reason"])
        self.assertFalse(result["comment_attempted"])
        self.assertEqual(page.events.count(("down", "left")), 1)
        self.assertEqual(page.events.count(("up", "left")), 1)
        self.assertEqual(result["like_diagnostics"]["down_requests"], 1)
        self.assertEqual(result["like_diagnostics"]["up_requests"], 1)
        self.assertEqual(result["like_diagnostics"]["observed_clicks"], 1)
        self.assertIn(True, result["like_diagnostics"]["states"])
        self.assertIs(result["like_diagnostics"]["states"][-1], False)
        page.probes[0].dispose.assert_called_once()

    def test_success_requires_a_bounded_observation_period(self):
        page = TimedTargetVideoPage()
        result = self.run_video(page)
        self.assertTrue(result["liked"])
        self.assertGreaterEqual(sum(page.waits), 2500)
        self.assertLessEqual(sum(page.waits), 4000)
        self.assertEqual(page.events.count(("click", "like")), 1)

    def test_final_check_applies_even_when_comments_are_disabled(self):
        page = TimedTargetVideoPage()
        # Isolate the final check from the initial confirmation window: the state
        # reverts during the normal pause between liking and the comment decision.
        def click_once(*args, **kwargs):
            page.like.receive_click()
            return True, "liked", True
        with patch.object(engagement, "_like_target_video", side_effect=click_once):
            page.revert_at_ms = 700
            result = self.run_video(page)
        self.assertFalse(result["liked"])
        self.assertIn("reverted", result["like_reason"])
        self.assertEqual(page.events.count(("click", "like")), 1)

    def test_unknown_colored_heart_and_static_like_label_never_permit_click(self):
        page = TimedTargetVideoPage()
        page.liked = True
        original_evaluate = page.like.evaluate
        def snapshot(script, point=None):
            if "pressed:" in script:
                return {"pressed": None, "label": "Like", "text": "", "marker": "like-icon",
                        "fills": ["color(srgb 1 0.2 0.4)"], "heart_fills": ["color(srgb 1 0.2 0.4)"]}
            return original_evaluate(script, point)
        with patch.object(page.like, "evaluate", side_effect=snapshot), \
                patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(engagement, "human_pause"):
            result = engagement._like_target_video(page, MouseState())
        self.assertTrue(page.liked)
        self.assertFalse(result[2])
        self.assertEqual(page.events, [])

    def test_unrecognized_heart_color_cannot_be_overridden_by_unpressed_attribute(self):
        button = MagicMock()
        button.evaluate.return_value = {
            "pressed": "false", "label": "Like", "text": "", "marker": "like-icon",
            "fills": ["rgb(255,51,102)"], "heart_fills": ["rgb(255,51,102)"],
        }
        self.assertIsNone(target_page.toggle_state(button, "like"))

    def test_generic_like_label_without_state_or_identified_heart_is_unknown(self):
        button = MagicMock()
        button.evaluate.return_value = {
            "pressed": None, "label": "Like", "text": "", "marker": "",
            "fills": [], "heart_fills": [],
        }
        self.assertIsNone(target_page.toggle_state(button, "like"))

    def test_confirmation_tolerates_initial_loading_but_not_a_later_reversion(self):
        cases = [
            ([False, False, True, True, True, True], (True, "liked")),
            ([True, True, False], (False, "state_reverted")),
            ([True, True, True, True, True, None], (False, "state_unconfirmed")),
            ([None] * 6, (False, "state_unconfirmed")),
            ([False] * 6, (False, "state_unconfirmed")),
        ]
        for states, expected in cases:
            with self.subTest(states=states):
                page = TimedTargetVideoPage()
                diagnostics = {"states": []}
                with patch.object(engagement, "target_like_button", return_value=page.like), \
                        patch.object(engagement, "toggle_state", side_effect=states):
                    result = engagement._confirm_target_like(page, page.url, diagnostics)
                self.assertEqual(result, expected)
                self.assertEqual(diagnostics["states"], states)
                self.assertEqual(page.events, [])

    def test_confirmation_aborts_when_the_video_changes(self):
        page = TimedTargetVideoPage()
        expected_url = page.url
        def changed_video(_milliseconds):
            page.url = "https://www.tiktok.com/@other/video/999"
        with patch.object(page, "wait_for_timeout", side_effect=changed_video), \
                patch.object(engagement, "target_like_button") as find_button:
            result = engagement._confirm_target_like(page, expected_url, {"states": []})
        self.assertEqual(result, (False, "video_changed_during_confirmation"))
        find_button.assert_not_called()

    @patch.object(engagement, "human_pause")
    def test_already_liked_path_does_not_wait_or_add_listeners(self, _pause):
        page = TimedTargetVideoPage()
        page.liked = True
        with patch.object(engagement, "target_like_button", return_value=page.like):
            self.assertEqual(engagement._like_target_video(page, MouseState()), (False, "already_liked", False))
        self.assertEqual(page.waits, [])
        self.assertEqual(page.probes, [])

    @patch.object(engagement, "human_pause")
    def test_event_observer_is_removed_even_when_mouse_acknowledgement_is_lost(self, _pause):
        page = TimedTargetVideoPage()
        diagnostics = {}
        original_up = page.mouse.up
        def uncertain_up(**kwargs):
            original_up(**kwargs)
            raise TimeoutError("lost mouse acknowledgement")
        with patch.object(page.mouse, "up", side_effect=uncertain_up), \
                patch.object(engagement, "target_like_button", return_value=page.like):
            result = engagement._like_target_video(page, MouseState(), diagnostics=diagnostics)
        self.assertEqual(result, (False, "click_unconfirmed", True))
        self.assertEqual(diagnostics["observed_clicks"], 1)
        page.probes[0].dispose.assert_called_once()

    def test_reversion_is_persisted_as_a_like_failure_with_click_diagnostics(self):
        page = TimedTargetVideoPage(revert_at_ms=1400)
        config = {"target_accounts": {
            "enabled": True, "participants": ["acc"], "handles": ["brand"],
            "like_probability": 1, "comment_probability": 0,
        }}
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        runtime.initialize_db_schema(conn)
        with patch.object(target, "navigate_target_page", return_value=(True, "ok")), \
                patch.object(target, "fetch_recent_videos", return_value=["101"]), \
                patch.object(target, "load_comment_file", return_value=[]), \
                patch.object(target, "session_log"), patch.object(target, "human_pause"), \
                patch.object(engagement, "_open_target_video", return_value=(True, "ok")), \
                patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(engagement.time, "sleep"):
            counts = target.run_target_engagement(page, {"id": "acc"}, config, conn)
        self.assertEqual(counts["likes"], 0)
        self.assertEqual(counts["like_failures"], 1)
        self.assertEqual(conn.execute("SELECT liked FROM target_engagements").fetchone()[0], 0)
        status, detail = conn.execute("SELECT status, detail FROM action_log WHERE action='target_like'").fetchone()
        self.assertEqual(status, "fail")
        self.assertIn("reason=state_reverted", detail)
        self.assertIn("down_requests=1 up_requests=1 observed_clicks=1", detail)
        self.assertIn("states=liked,liked,unliked", detail)


if __name__ == "__main__":
    unittest.main()
