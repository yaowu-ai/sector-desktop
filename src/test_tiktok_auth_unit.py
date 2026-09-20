import unittest
from unittest.mock import MagicMock, patch

from auth_adapters import AuthResult, LoginState
from platforms.tiktok.auth import TikTokAuthAdapter


class TikTokAuthTests(unittest.TestCase):
    @patch("platforms.tiktok.auth.time.sleep")
    @patch("platforms.tiktok.auth.classify_tiktok_page")
    @patch("platforms.tiktok.auth.navigate_tiktok_page")
    def test_retries_unknown_state_before_returning(
        self,
        navigate_tiktok_page,
        classify_tiktok_page,
        sleep,
    ):
        page = MagicMock()
        classify_tiktok_page.side_effect = [
            AuthResult(
                platform="tiktok",
                state=LoginState.UNKNOWN,
                detail="page is still loading",
            ),
            AuthResult(
                platform="tiktok",
                state=LoginState.LOGGED_IN,
                detail="interactive TikTok controls detected (1)",
            ),
        ]

        result = TikTokAuthAdapter().ensure_logged_in(
            page,
            {"id": "tiktok_73"},
            {},
        )

        self.assertEqual(result.state, LoginState.LOGGED_IN)
        self.assertEqual(classify_tiktok_page.call_count, 2)
        sleep.assert_called_once()
        navigate_tiktok_page.assert_called_once()


if __name__ == "__main__":
    unittest.main()
