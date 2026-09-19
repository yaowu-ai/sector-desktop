import unittest
from unittest.mock import MagicMock

from ixbrowser import IXBrowserClient, _api_target, _sdk_profile_id


class FakeSDK:
    def __init__(self):
        self.code = None
        self.message = None
        self.total = 3
        self.opened = []
        self.native_opened = []

    def get_profile_list(self, keyword=None, page=1, limit=10):
        rows = {
            1: [
                {"profile_id": 11, "name": "tiktok_1"},
                {"profile_id": 12, "name": "tiktok_2"},
            ],
            2: [{"profile_id": 13, "name": "tiktok_3"}],
        }.get(page, [])
        return rows

    def get_opened_profile_list(self):
        return self.opened

    def get_native_opened_profile_list(self):
        return self.native_opened

    def open_profile(self, profile_id, **kwargs):
        self.open_call = (profile_id, kwargs)
        return {"debugging_address": "127.0.0.1:9222"}

    def close_profile(self, profile_id):
        self.close_call = profile_id
        return True


class IXBrowserAdapterTests(unittest.TestCase):
    def test_api_target_accepts_host_and_api_path(self):
        self.assertEqual(_api_target("127.0.0.1:53201"), ("127.0.0.1", 53201))
        self.assertEqual(
            _api_target("http://localhost:53200/api/v2/"),
            ("localhost", 53200),
        )

    def test_api_target_rejects_unsupported_values(self):
        with self.assertRaisesRegex(ValueError, "只支持"):
            _api_target("http://localhost:53200/wrong")
        with self.assertRaisesRegex(ValueError, "无效"):
            _api_target("https://localhost:53200")

    def test_profile_id_must_be_numeric(self):
        with self.assertRaisesRegex(ValueError, "无效的 ixBrowser profile_id"):
            _sdk_profile_id("profile-3")

    def test_list_browsers_paginates_and_normalizes_ids(self):
        client = IXBrowserClient(sdk_client=FakeSDK())

        profiles = client.list_browsers(name="tiktok_", page_size=2)

        self.assertEqual([profile["id"] for profile in profiles], ["11", "12", "13"])

    def test_open_browser_returns_http_cdp_endpoint(self):
        sdk = FakeSDK()
        client = IXBrowserClient(sdk_client=sdk)

        endpoint = client.open_browser("11")

        self.assertEqual(endpoint, "http://127.0.0.1:9222")
        self.assertEqual(sdk.open_call[0], 11)

    def test_is_open_checks_manual_profiles(self):
        sdk = FakeSDK()
        sdk.native_opened = [{"profile_id": 22}]

        self.assertTrue(IXBrowserClient(sdk_client=sdk).is_open("22"))
        self.assertFalse(IXBrowserClient(sdk_client=sdk).is_open("23"))

    def test_provider_client_can_be_constructed_with_fake_sdk(self):
        sdk = MagicMock()
        client = IXBrowserClient(sdk_client=sdk)
        self.assertIs(client.sdk, sdk)


if __name__ == "__main__":
    unittest.main()
