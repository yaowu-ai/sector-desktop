import unittest
from unittest.mock import MagicMock, patch

from auth_adapters import AuthResult, LoginState
from platforms.tiktok.auth import TikTokAuthAdapter


class TikTokAuthTests(unittest.TestCase):
    def test_navigation_timeout_uses_visible_auth_state_only_on_tiktok(self):
        for state in (LoginState.LOGGED_IN, LoginState.LOGGED_OUT, LoginState.CAPTCHA, LoginState.UNKNOWN):
            with self.subTest(state=state):
                page = MagicMock(url='https://www.tiktok.com/foryou')
                observed = AuthResult(platform='tiktok', state=state, detail='observed state')
                with patch('platforms.tiktok.auth.navigate_tiktok_page', side_effect=TimeoutError('load timeout')), \
                     patch('platforms.tiktok.auth.classify_tiktok_page', return_value=observed):
                    result = TikTokAuthAdapter().ensure_logged_in(page, {'id':'account'}, {})
                self.assertEqual(result.state, state)
                if state == LoginState.UNKNOWN:
                    self.assertEqual(result.error_code, 'AUTH_TIKTOK_LOAD_FAILED')
                    self.assertIn('load timeout', result.detail)
                else:
                    self.assertIs(result, observed)

    def test_failed_navigation_never_accepts_unrelated_page_as_logged_in(self):
        for url, failure in (('https://example.com', TimeoutError('timeout')),
                             ('https://www.tiktok.com/foryou', RuntimeError('net::ERR_PROXY_CONNECTION_FAILED'))):
            with self.subTest(url=url), \
                 patch('platforms.tiktok.auth.navigate_tiktok_page', side_effect=failure), \
                 patch('platforms.tiktok.auth.classify_tiktok_page') as classify:
                result = TikTokAuthAdapter().ensure_logged_in(MagicMock(url=url), {'id':'account'}, {})
                self.assertEqual(result.error_code, 'AUTH_TIKTOK_LOAD_FAILED')
                classify.assert_not_called()

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
