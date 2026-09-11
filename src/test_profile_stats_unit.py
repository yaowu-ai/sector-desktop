import unittest
from unittest.mock import MagicMock, patch

from profile_stats import (
    LikedPages,
    collect,
    collect_profile_snapshot,
    logged_in_handle,
    parse_stats,
    profile_handle,
)


class ProfileStatsTests(unittest.TestCase):
    def test_existing_login_avoids_denied_homepage(self):
        context = MagicMock()
        browser = MagicMock(contexts=[context])
        existing = MagicMock(url="https://www.tiktok.com/@someone_else?lang=en-GB")
        context.pages = [existing]
        page = context.new_page.return_value

        def navigate(url, **kwargs):
            if url == "https://www.tiktok.com/?lang=en-GB":
                raise RuntimeError("Access Denied on homepage")
            page.url = url

        page.goto.side_effect = navigate
        with patch("profile_stats.logged_in_handle", return_value="ralphrivera448"), \
                patch("profile_stats.read_stats", return_value={"followers": 3}), \
                patch("profile_stats.read_liked", return_value={"liked": 4}), \
                patch("profile_stats.read_activity", return_value={}):
            result = collect(browser)
        self.assertEqual(result["handle"], "ralphrivera448")
        page.goto.assert_called_once_with("https://www.tiktok.com/@ralphrivera448?lang=en-GB",
                                          wait_until="domcontentloaded", timeout=30000)
        existing.goto.assert_not_called()
        existing.close.assert_not_called()
        page.close.assert_called_once()

    def test_navigation_identifies_login_not_viewed_profile(self):
        page = MagicMock(url="https://www.tiktok.com/@someone_else")
        link = MagicMock()
        link.get_attribute.return_value = "/@logged_in_user?lang=en-GB"
        page.get_by_role.return_value.all.return_value = [link]
        self.assertEqual(logged_in_handle(page, 1), "logged_in_user")

    def test_missing_login_does_not_fall_back_to_viewed_profile(self):
        page = MagicMock(url="https://www.tiktok.com/@mabilqadri")
        page.get_by_role.return_value.all.return_value = []
        with patch("profile_stats.time.monotonic", side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(RuntimeError, "未识别到"):
                logged_in_handle(page, 1)

    def test_default_collects_login_and_closes_only_temporary_tab(self):
        browser = MagicMock()
        context = MagicMock()
        browser.contexts = [context]
        page = context.new_page.return_value
        page.goto.side_effect = lambda url, **kwargs: setattr(page, "url", url)
        with patch("profile_stats.logged_in_handle", return_value="my_account"), \
                patch("profile_stats.read_stats", return_value={"likes": 175}), \
                patch("profile_stats.read_liked", return_value={"liked": 4}), \
                patch("profile_stats.read_activity", return_value={"has_liked_your_comment": False}):
            result = collect(browser)
        self.assertEqual(result["handle"], "my_account")
        self.assertEqual(result["liked"], 4)
        self.assertEqual(page.url, "https://www.tiktok.com/@my_account?lang=en-GB")
        page.close.assert_called_once()
        browser.close.assert_not_called()

    def test_account_switch_rejects_result_and_cleans_up(self):
        browser = MagicMock()
        context = MagicMock()
        browser.contexts = [context]
        page = context.new_page.return_value
        page.goto.side_effect = lambda url, **kwargs: setattr(page, "url", url)
        with patch("profile_stats.logged_in_handle", side_effect=["first", "second"]), \
                patch("profile_stats.read_stats", return_value={"likes": 175}), \
                patch("profile_stats.read_liked", return_value={"liked": 4}), \
                patch("profile_stats.read_activity", return_value={"has_liked_your_comment": False}):
            with self.assertRaisesRegex(RuntimeError, "发生变化"):
                collect(browser)
        page.close.assert_called_once()

    def test_multiple_sessions_require_targeted_connection(self):
        browser = MagicMock(contexts=[MagicMock(), MagicMock()])
        with self.assertRaisesRegex(RuntimeError, "唯一浏览器会话"):
            collect(browser)

    def test_collect_profile_snapshot_returns_success_envelope(self):
        browser = MagicMock()
        account = {"id": "acc-1", "platform": "tiktok"}
        with patch("profile_stats.collect", return_value={
            "handle": "my_account",
            "followers": 3,
            "collected_at": "2026-09-10T07:08:30+00:00",
        }):
            result = collect_profile_snapshot(browser, account, timeout=5)
        self.assertEqual(result["account_id"], "acc-1")
        self.assertEqual(result["platform"], "tiktok")
        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["error"])
        self.assertEqual(result["handle"], "my_account")

    def test_collect_profile_snapshot_returns_failure_envelope(self):
        browser = MagicMock()
        account = {"id": "acc-1", "platform": "tiktok"}
        with patch("profile_stats.collect", side_effect=RuntimeError("boom")):
            result = collect_profile_snapshot(browser, account, timeout=5)
        self.assertEqual(result["account_id"], "acc-1")
        self.assertEqual(result["platform"], "tiktok")
        self.assertEqual(result["status"], "failed")
        self.assertIn("RuntimeError: boom", result["error"])
        self.assertIn("collected_at", result)

    def test_current_profile(self):
        result = parse_stats("58 Following 33 Followers 175 Likes")
        self.assertEqual([result[k] for k in ("following", "followers", "likes")],
                         [58, 33, 175])
        self.assertEqual(result["approximate_fields"], [])

    def test_rounded_counts_preserve_display_value(self):
        result = parse_stats("1,234\nFollowing\n1.2K Followers 3.4M Likes")
        self.assertEqual(result["following"], 1234)
        self.assertEqual(result["followers"], 1200)
        self.assertEqual(result["likes"], 3400000)
        self.assertEqual(result["raw"]["followers"], "1.2K")
        self.assertEqual(result["approximate_fields"], ["followers", "likes"])

    def test_missing_or_unrelated_content_is_not_zero(self):
        for text in ("", "58 Following 33 Followers", "Log in", "- Followers",
                     "video: 58 Following 33 Followers 175 Likes", "1,2 Following 3 Followers 4 Likes"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_stats(text)
        self.assertEqual(parse_stats("0 Following 0 Followers 0 Likes")["likes"], 0)

    def test_only_exact_tiktok_profile_is_reused(self):
        self.assertEqual(profile_handle("https://www.tiktok.com/@mabilqadri?lang=en-GB"),
                         "mabilqadri")
        for url in ("https://example.com/@mabilqadri", "https://www.tiktok.com/@mabilqadri/video/123",
                    "https://www.tiktok.com/@mabilqadri_other/video/123"):
            self.assertIsNone(profile_handle(url))


class LikedPagesTests(unittest.TestCase):
    def test_multiple_pages_deduplicate_and_require_end(self):
        state = LikedPages()
        state.accept("0", {"statusCode": 0, "itemList": [{"id": "1"}, {"id": "2"}],
                           "hasMore": True, "cursor": "next"})
        self.assertIsNone(state.result()["liked"])
        self.assertEqual(state.result()["liked_loaded"], 2)
        state.accept("next", {"statusCode": 0, "itemList": [{"id": "2"}, {"id": "3"}],
                              "hasMore": False})
        self.assertEqual(state.result()["liked"], 3)
        self.assertTrue(state.result()["liked_complete"])

    def test_missing_first_page_cannot_report_complete(self):
        state = LikedPages()
        state.accept("next", {"statusCode": 0, "itemList": [{"id": "3"}], "hasMore": False})
        self.assertIsNone(state.result()["liked"])

    def test_explicit_empty_is_zero_but_error_is_unknown(self):
        state = LikedPages()
        state.accept("0", {"statusCode": 0, "hasMore": False})
        self.assertEqual(state.result()["liked"], 0)
        for data in ({"statusCode": 102}, {"statusCode": 0},
                     {"statusCode": 0, "hasMore": False, "itemList": [{}]}):
            state = LikedPages()
            state.accept("0", data)
            self.assertIsNone(state.result()["liked"])
            self.assertFalse(state.result()["liked_complete"])

    def test_stuck_cursor_cannot_report_total(self):
        state = LikedPages()
        state.accept("0", {"statusCode": 0, "itemList": [{"id": "1"}],
                           "hasMore": True, "cursor": "0"})
        self.assertIsNone(state.result()["liked"])
        self.assertEqual(state.result()["liked_status"], "liked_cursor_not_advancing")


if __name__ == "__main__":
    unittest.main()
