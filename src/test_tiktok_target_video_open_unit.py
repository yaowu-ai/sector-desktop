import unittest
from unittest.mock import MagicMock, patch

from platforms.tiktok.engagement import engage_target_video
from platforms.tiktok.target import run_target_engagement


class FakeTargetVideoPage:
    def __init__(self, url):
        self.url = url
        self.viewport_size = {"width": 1280, "height": 800}
        self.goto_calls = []
        self.locator_calls = []

    def goto(self, url, timeout, **_kwargs):
        self.goto_calls.append((url, timeout))

    def locator(self, selector):
        self.locator_calls.append(selector)
        locator = MagicMock(name=f"locator:{selector}")
        locator.count.return_value = 0
        return locator


class TikTokTargetVideoOpenTests(unittest.TestCase):
    @patch("platforms.tiktok.engagement.time.sleep")
    @patch("platforms.tiktok.engagement.human_pause")
    @patch("platforms.tiktok.engagement._comment_on_video_page")
    @patch("platforms.tiktok.engagement._like_target_video")
    def test_navigation_mismatch_skips_like_and_comment(
        self,
        try_like,
        comment,
        _human_pause,
        _sleep,
    ):
        page = FakeTargetVideoPage("https://www.tiktok.com/@target")
        try_like.return_value = (False, "button_not_found", False)

        with patch("platforms.tiktok.engagement.random.random", side_effect=[0.0, 0.0]):
            result = engage_target_video(
                page,
                "target",
                "123",
                ["hello"],
                like_prob=1.0,
                comment_prob=1.0,
            )

        self.assertFalse(result["opened"])
        self.assertEqual(result["open_reason"], "url_mismatch")
        try_like.assert_not_called()
        comment.assert_not_called()

    @patch("platforms.tiktok.target.human_pause")
    @patch("platforms.tiktok.target.navigate_target_page", return_value=(True, "ok"))
    @patch("platforms.tiktok.target.log_action")
    @patch("platforms.tiktok.target.record_target_engagement")
    @patch("platforms.tiktok.target.engage_target_video")
    @patch("platforms.tiktok.target.fetch_recent_videos", return_value=["123"])
    @patch("platforms.tiktok.target.load_comment_file", return_value=["hello"])
    def test_open_failure_does_not_record_engagement_or_watermark(
        self,
        _load_comments,
        _fetch_recent,
        engage,
        record_engagement,
        log_action,
        _open_profile,
        _human_pause,
    ):
        engage.return_value = {
            "opened": False,
            "open_reason": "url_mismatch",
            "liked": False,
            "commented": False,
        }
        config = {
            "platforms": {
                "tiktok": {
                    "target_engagement": {
                        "enabled": True,
                        "participants": ["account-1"],
                        "handles": ["target"],
                        "first_run_latest_n": 1,
                        "max_videos_per_run": 3,
                    },
                    "comments": {"target_file": "comments_brand.txt"},
                }
            }
        }

        run_target_engagement(MagicMock(), {"id": "account-1"}, config, MagicMock())

        record_engagement.assert_not_called()
        self.assertTrue(
            any(
                call.args[3:5] == ("target_engage", "error")
                for call in log_action.call_args_list
            )
        )
        self.assertFalse(
            any(call.args[3] == "target_watermark" for call in log_action.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
