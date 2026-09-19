import unittest
from unittest.mock import MagicMock

from platforms.tiktok.navigation import navigate_tiktok_page


class TikTokNavigationTests(unittest.TestCase):
    def test_retries_network_failures_up_to_three_times_with_30_second_timeout(self):
        page = MagicMock(name="page")
        page.goto.side_effect = [
            Exception("net::ERR_SOCKS_CONNECTION_FAILED"),
            TimeoutError("navigation timed out"),
            Exception("net::ERR_CONNECTION_RESET"),
            None,
        ]

        result = navigate_tiktok_page(page)

        self.assertIs(result, page)
        self.assertEqual(page.goto.call_count, 4)
        self.assertEqual(
            [call.kwargs["timeout"] for call in page.goto.call_args_list],
            [30000, 30000, 30000, 30000],
        )

    def test_does_not_retry_non_network_navigation_errors(self):
        page = MagicMock(name="page")
        page.goto.side_effect = Exception("page was closed")

        with self.assertRaisesRegex(Exception, "page was closed"):
            navigate_tiktok_page(page)

        page.goto.assert_called_once()

    def test_raises_the_final_network_error_after_three_retries(self):
        page = MagicMock(name="page")
        page.goto.side_effect = [
            Exception("net::ERR_SOCKS_CONNECTION_FAILED"),
            Exception("net::ERR_SOCKS_CONNECTION_FAILED"),
            Exception("net::ERR_SOCKS_CONNECTION_FAILED"),
            Exception("net::ERR_SOCKS_CONNECTION_FAILED final"),
        ]

        with self.assertRaisesRegex(Exception, "final"):
            navigate_tiktok_page(page)

        self.assertEqual(page.goto.call_count, 4)

    def test_waits_for_domcontentloaded_with_the_same_30_second_timeout(self):
        page = MagicMock(name="page")

        navigate_tiktok_page(page, wait_for_domcontentloaded=True)

        page.wait_for_load_state.assert_called_once_with(
            "domcontentloaded",
            timeout=30000,
        )


if __name__ == "__main__":
    unittest.main()
