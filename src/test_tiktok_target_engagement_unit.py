import sqlite3
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from core import runtime
from platforms.tiktok import engagement, target
from platforms.tiktok import target_page


class TargetEngagementRegressionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        runtime.initialize_db_schema(self.conn)
        self.addCleanup(self.conn.close)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("human_pause", "session_log"):
            self.stack.enter_context(patch.object(target, name))
        self.stack.enter_context(patch.object(target, "navigate_target_page", return_value=(True, "ok")))
        self.stack.enter_context(patch.object(target, "load_comment_file", return_value=["hello"]))
        self.config = {"target_accounts": {
            "enabled": True, "participants": ["acc"], "handles": ["brand"],
            "first_run_latest_n": 3, "max_videos_per_run": 3,
        }}

    def run_target(self):
        return target.run_target_engagement(MagicMock(), {"id": "acc"}, self.config, self.conn)

    def test_later_video_cannot_move_watermark_past_a_failed_open(self):
        runtime.record_target_engagement(self.conn, "tiktok", "acc", "brand", "100", True, False)
        with patch.object(target, "fetch_recent_videos", return_value=["103", "102", "101"]), \
                patch.object(target, "engage_target_video", side_effect=[
                    {"opened": False, "open_reason": "maintenance_page"},
                    {"opened": True, "liked": True, "commented": False},
                    {"opened": True, "liked": True, "commented": False},
                ]) as engage:
            self.run_target()
        self.assertEqual(engage.call_count, 1)
        self.assertEqual(runtime.get_target_watermark(self.conn, "tiktok", "acc", "brand"), 100)

    def test_already_liked_is_skipped_and_not_counted_as_failure(self):
        with patch.object(target, "fetch_recent_videos", return_value=["101"]), \
                patch.object(target, "engage_target_video", return_value={
                    "opened": True, "liked": False, "like_attempted": True,
                    "like_reason": "already_liked", "commented": False,
                }):
            counts = self.run_target()
        self.assertEqual(counts["like_failures"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT status FROM action_log WHERE action='target_like'"
        ).fetchone()[0], "skip")

    def test_follow_happens_before_video_discovery_and_config_limits_still_apply(self):
        events = []
        self.config["target_accounts"].update({"follow": True, "follow_probability": 1.0,
                                               "first_run_latest_n": 2, "max_videos_per_run": 1})
        with patch.object(target, "follow_target_profile", side_effect=lambda *a: events.append("follow") or "already"), \
                patch.object(target, "fetch_recent_videos", side_effect=lambda *a: events.append("fetch") or ["103", "102"]), \
                patch.object(target, "engage_target_video", return_value={
                    "opened": True, "liked": False, "commented": True,
                }) as engage:
            counts = self.run_target()
        self.assertEqual(events, ["follow", "fetch"])
        self.assertEqual(engage.call_count, 1)
        self.assertEqual(engage.call_args.args[2], "103")
        self.assertEqual(counts["follows"], 0)
        self.assertEqual(counts["comments"], 1)
        self.assertTrue(runtime.has_followed_target(self.conn, "tiktok", "acc", "brand"))

    def test_failed_open_stops_only_that_handle(self):
        self.config["target_accounts"]["handles"] = ["brand", "other"]
        with patch.object(target, "fetch_recent_videos", return_value=["101"]), \
                patch.object(target, "engage_target_video", side_effect=[
                    {"opened": False, "open_reason": "maintenance_page"},
                    {"opened": True, "liked": True, "commented": False},
                ]) as engage:
            counts = self.run_target()
        self.assertEqual(engage.call_count, 2)
        self.assertEqual(counts["videos"], 1)
        self.assertIsNone(runtime.get_target_watermark(self.conn, "tiktok", "acc", "brand"))
        self.assertEqual(runtime.get_target_watermark(self.conn, "tiktok", "acc", "other"), 101)

    def test_backlog_is_processed_oldest_first_before_applying_run_limit(self):
        runtime.record_target_engagement(self.conn, "tiktok", "acc", "brand", "100", True, False)
        self.config["target_accounts"]["max_videos_per_run"] = 2
        with patch.object(target, "fetch_recent_videos", return_value=["104", "103", "102", "101"]), \
                patch.object(target, "engage_target_video", return_value={
                    "opened": True, "liked": True, "commented": False,
                }) as engage:
            self.run_target()
        self.assertEqual([call.args[2] for call in engage.call_args_list], ["101", "102"])
        self.assertEqual(runtime.get_target_watermark(self.conn, "tiktok", "acc", "brand"), 102)

    def test_disabled_or_nonparticipant_never_opens_browser_page(self):
        self.config["target_accounts"]["enabled"] = False
        self.run_target()
        self.config["target_accounts"].update({"enabled": True, "participants": []})
        self.run_target()
        target.navigate_target_page.assert_not_called()


class TargetVideoDiscoveryRegressionTests(unittest.TestCase):
    @patch.object(engagement, "human_pause")
    def test_only_video_links_owned_by_the_target_are_collected(self, _pause):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand"
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        anchors = page.locator.return_value
        anchors.count.return_value = 2
        anchors.nth.side_effect = lambda index: self.anchor([
            "https://www.tiktok.com/@other/video/999",
            "/@brand/video/101",
        ][index])
        self.assertEqual(engagement.fetch_recent_videos(page, "brand"), ["101"])

    @patch.object(engagement, "human_pause")
    def test_missing_video_grid_is_scrolled_and_scan_is_bounded(self, _pause):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand"
        page.viewport_size = {"width": 1280, "height": 800}
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        anchors = page.locator.return_value
        anchors.count.side_effect = [0, 0, 1]
        anchors.nth.return_value = self.anchor("/@brand/video/101")
        self.assertEqual(engagement.fetch_recent_videos(page, "brand"), ["101"])
        self.assertEqual(page.mouse.wheel.call_count, 2)
        page.mouse.wheel.reset_mock()
        anchors.count.side_effect = None
        anchors.count.return_value = 0
        self.assertEqual(engagement.fetch_recent_videos(page, "brand"), [])
        self.assertEqual(page.mouse.wheel.call_count, target_page.MAX_PROFILE_SCROLLS)

    @patch.object(engagement, "recover_target_page", return_value=(True, "ok"))
    @patch.object(engagement, "human_pause")
    def test_video_card_below_recommendations_is_scrolled_and_clicked(self, _pause, recover):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand"
        anchors = page.locator.return_value
        anchors.count.return_value = 1
        link = self.anchor("/@brand/video/101")
        link.get_attribute.side_effect = lambda name, **k: "/@brand/video/101" if name == "href" else None
        anchors.nth.return_value = link
        link.click.side_effect = lambda **k: setattr(page, "url", "https://www.tiktok.com/@brand/video/101")
        self.assertEqual(engagement._open_target_video(page, "brand", "101"), (True, "ok"))
        link.scroll_into_view_if_needed.assert_called_once()
        link.click.assert_called_once()
        page.goto.assert_not_called()
        recover.assert_called_once_with(page, "brand", "101")

    @staticmethod
    def anchor(href):
        anchor = MagicMock()
        anchor.get_attribute.return_value = href
        return anchor


class TargetPageRecoveryTests(unittest.TestCase):
    @patch.object(target_page, "target_page_state", return_value=(True, "ok"))
    def test_ready_page_does_not_wait_or_reload(self, _state):
        page = MagicMock()
        self.assertEqual(target_page.recover_target_page(page, "brand", "101"), (True, "ok"))
        page.wait_for_timeout.assert_not_called()
        page.reload.assert_not_called()
        page.locator.assert_not_called()

    @patch.object(target_page, "target_page_state")
    def test_maintenance_can_recover_without_reload(self, state):
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = "Oops! Something went wrong"
        page.title.return_value = "Site Maintenance"
        state.side_effect = [(False, "video_not_ready"), (True, "ok")]
        self.assertEqual(target_page.recover_target_page(page, "brand", "101"), (True, "ok"))
        page.reload.assert_not_called()
        page.wait_for_timeout.assert_called_once()

    @patch.object(target_page, "target_page_state")
    def test_maintenance_reloads_once_then_recovers(self, state):
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = "Oops! Something went wrong"
        page.title.return_value = "Site Maintenance"
        state.side_effect = [(False, "video_not_ready")] * 4 + [(True, "ok")]
        self.assertEqual(target_page.recover_target_page(page, "brand", "101"), (True, "ok"))
        page.reload.assert_called_once_with(wait_until="domcontentloaded", timeout=30000)

    @patch.object(target_page, "target_page_state", return_value=(False, "video_not_ready"))
    def test_persistent_maintenance_has_finite_waits_and_one_reload(self, _state):
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = "Oops! Something went wrong"
        self.assertEqual(target_page.recover_target_page(page, "brand", "101"), (False, "maintenance_page"))
        self.assertEqual(page.wait_for_timeout.call_count, target_page.RECOVERY_POLLS * 2)
        page.reload.assert_called_once()

    @patch.object(target_page, "target_page_state", return_value=(False, "video_not_ready"))
    def test_verification_page_is_skipped_without_refresh(self, _state):
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = "Verify you are human"
        self.assertEqual(target_page.recover_target_page(page, "brand", "101"), (False, "verification_required"))
        page.reload.assert_not_called()
        page.wait_for_timeout.assert_not_called()


class TargetControlTests(unittest.TestCase):
    @staticmethod
    def control(pressed=None, label="", text="", marker="", fills=()):
        btn = MagicMock()
        btn.evaluate.return_value = dict(pressed=pressed, label=label, text=text, marker=marker, fills=fills)
        btn.element_handle.return_value = btn
        return btn

    def test_toggle_states_support_labels_icon_fill_and_unknown(self):
        cases = [
            (self.control(pressed="true"), "like", True),
            (self.control(label="Unlike"), "like", True),
            (self.control(fills=["rgb(254,44,85)"]), "like", True),
            (self.control(pressed="false"), "like", False),
            (self.control(label="Like"), "like", None),
            (self.control(), "like", None),
            (self.control(pressed="false", fills=["rgb(254,44,85)"]), "like", None),
            (self.control(text="Following ✓"), "follow", True),
            (self.control(text="已关注"), "follow", True),
            (self.control(text="Follow"), "follow", False),
            (self.control(text="Message"), "follow", None),
        ]
        for btn, kind, expected in cases:
            with self.subTest(kind=kind, snapshot=btn.evaluate.return_value):
                self.assertIs(target_page.toggle_state(btn, kind), expected)

    @patch.object(engagement, "human_click_locator")
    def test_liked_or_uncertain_like_control_is_never_clicked(self, click):
        for btn, reason in [(self.control(label="Unlike"), "already_liked"),
                            (self.control(), "state_unknown")]:
            with patch.object(engagement, "target_like_button", return_value=btn):
                self.assertEqual(engagement._like_target_video(MagicMock(), MagicMock()), (False, reason, False))
            btn.click.assert_not_called()
        click.assert_not_called()

    @patch.object(engagement, "human_click_locator")
    def test_followed_or_unknown_profile_is_never_clicked(self, click):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand"
        for btn, status in [(self.control(text="Following ✓"), "already"),
                            (self.control(), "unknown")]:
            with patch.object(engagement, "profile_follow_button", return_value=btn):
                self.assertEqual(engagement.follow_target_profile(page, "brand"), status)
        click.assert_not_called()

    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "human_click_locator", return_value=True)
    def test_a_like_click_is_verified_and_never_repeated(self, click, _pause):
        button = self.control(pressed="false", label="Like")
        page = MagicMock()
        with patch.object(engagement, "target_like_button", side_effect=[button] + [
            self.control(label="Unlike") for _ in range(engagement.LIKE_CONFIRM_SAMPLES)
        ]), patch.object(engagement, "target_like_click_point", return_value={"x": 100, "y": 100}):
            self.assertEqual(engagement._like_target_video(page, MagicMock()), (True, "liked", True))
        button.click.assert_not_called()
        page.mouse.down.assert_called_once_with(button="left")
        page.mouse.up.assert_called_once_with(button="left")
        click.assert_not_called()

    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "human_click_locator")
    def test_comments_tab_is_selected_before_typing_and_submits_once(self, click, _pause):
        page, tab, box, post = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        tab.get_attribute.return_value = "false"
        post.get_attribute.return_value = None
        box.evaluate.side_effect = lambda script: "activeElement" in script
        box.inner_text.side_effect = ["", "hello", ""]
        events = []
        tab.click.side_effect = lambda **k: events.append("tab")
        box.fill.side_effect = lambda *a, **k: events.append("type")
        with patch.object(engagement, "unique_visible", side_effect=[tab, box, post]):
            self.assertTrue(engagement._comment_on_video_page(page, MagicMock(), "hello"))
        self.assertEqual(events, ["tab", "type"])
        click.assert_not_called()
        box.fill.assert_called_once_with("hello", timeout=2500)
        post.click.assert_called_once_with(timeout=2000)
        box.press.assert_not_called()

    @patch.object(engagement, "human_pause")
    def test_uncertain_comment_submit_does_not_fall_back_to_enter(self, _pause):
        page, box, post = MagicMock(), MagicMock(), MagicMock()
        box.evaluate.side_effect = lambda script: "activeElement" in script
        box.inner_text.side_effect = ["", "hello"]
        post.get_attribute.return_value = None
        post.click.side_effect = TimeoutError("submission outcome unknown")
        with patch.object(engagement, "unique_visible", side_effect=[None, None, box, post]):
            self.assertFalse(engagement._comment_on_video_page(page, MagicMock(), "hello"))
        box.press.assert_not_called()
        post.click.assert_called_once_with(timeout=2000)

    def test_unrelated_recommended_account_buttons_cannot_supply_profile_control(self):
        with patch.object(target_page, "profile_title", return_value=None):
            page = MagicMock()
            self.assertIsNone(target_page.profile_follow_button(page, "brand"))
            page.get_by_role.assert_not_called()

    def test_follow_button_far_below_profile_title_is_rejected(self):
        title, parent, button = MagicMock(), MagicMock(), MagicMock()
        title.bounding_box.return_value = {"y": 100}
        title.locator.return_value = parent
        parent.locator.return_value.count.return_value = 1
        parent.locator.return_value.nth.return_value = button
        button.bounding_box.return_value = {"y": 700}
        with patch.object(target_page, "profile_title", return_value=title):
            self.assertIsNone(target_page.profile_follow_button(MagicMock(), "brand"))
            button.bounding_box.return_value = {"y": 180}
            self.assertIs(target_page.profile_follow_button(MagicMock(), "brand"), button)

    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "human_click_locator", return_value=True)
    def test_follow_success_is_confirmed_from_target_header(self, click, _pause):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand"
        with patch.object(engagement, "profile_follow_button", side_effect=[
            self.control(text="Follow"), self.control(text="Following ✓"),
        ]):
            self.assertEqual(engagement.follow_target_profile(page, "brand"), "followed")
        click.assert_called_once()

    @patch.object(engagement, "human_pause")
    def test_disabled_comment_submit_never_presses_enter(self, _pause):
        page, box, post = MagicMock(), MagicMock(), MagicMock()
        box.evaluate.side_effect = lambda script: "activeElement" in script
        box.inner_text.side_effect = ["", "hello"]
        post.get_attribute.return_value = "true"
        with patch.object(engagement, "unique_visible", side_effect=[None, None, box, post]):
            self.assertFalse(engagement._comment_on_video_page(page, MagicMock(), "hello"))
        post.click.assert_not_called()
        box.press.assert_not_called()

    @patch.object(engagement, "human_pause")
    @patch.object(engagement.time, "sleep")
    @patch.object(engagement, "_open_target_video", return_value=(True, "ok"))
    @patch.object(engagement, "_like_target_video")
    @patch.object(engagement, "_comment_on_video_page")
    def test_zero_probabilities_disable_actions_and_preserve_watch_duration(
        self, comment, like, _open, sleep, _pause,
    ):
        page = MagicMock()
        page.url = "https://www.tiktok.com/@brand/video/101"
        result = engagement.engage_target_video(page, "brand", "101", ["hello"], 0.0, 0.0)
        self.assertTrue(result["opened"])
        like.assert_not_called()
        comment.assert_not_called()
        self.assertGreaterEqual(sleep.call_args.args[0], 5)
        self.assertLessEqual(sleep.call_args.args[0], 15)


if __name__ == "__main__":
    unittest.main()
