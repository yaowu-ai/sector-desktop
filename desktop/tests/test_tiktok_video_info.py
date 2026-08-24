import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from platforms.tiktok.video_info import (
    capture_active_video_info,
    clean_text,
    clean_title,
    clean_url,
    parse_author_url,
    parse_tiktok_video_url,
)


class FakePage:
    def __init__(self, url="", dom_result=None, error=None):
        self.url = url
        self.dom_result = dom_result or {}
        self.error = error
        self.evaluate_calls = []

    def evaluate(self, script, arg=None):
        self.evaluate_calls.append((script, arg))
        if self.error:
            raise self.error
        return self.dom_result


class TikTokVideoInfoTests(unittest.TestCase):
    def test_parse_tiktok_video_url_extracts_handle_id_and_safe_url(self):
        parsed = parse_tiktok_video_url(
            "https://www.tiktok.com/@demo.creator/video/7390000000000000000?lang=en#share"
        )

        self.assertEqual(parsed["author_handle"], "demo.creator")
        self.assertEqual(parsed["video_id"], "7390000000000000000")
        self.assertEqual(
            parsed["video_url"],
            "https://www.tiktok.com/@demo.creator/video/7390000000000000000",
        )

    def test_parse_author_url_accepts_relative_profile_links(self):
        parsed = parse_author_url("/@brand_account?refer=feed")

        self.assertEqual(parsed["author_handle"], "brand_account")

    def test_clean_helpers_normalize_and_filter_generic_values(self):
        self.assertEqual(clean_text(" hello\n\nworld\t ", 20), "hello world")
        self.assertEqual(clean_url("/@demo/video/123?token=secret"), "https://www.tiktok.com/@demo/video/123")
        self.assertEqual(
            clean_url("//www.tiktok.com/@demo/video/123?token=secret"),
            "https://www.tiktok.com/@demo/video/123",
        )
        self.assertIsNone(clean_url("blob:https://www.tiktok.com/abc"))
        self.assertIsNone(clean_title("TikTok - Make Your Day"))
        self.assertEqual(clean_title("Real caption #tag"), "Real caption #tag")

    def test_capture_active_video_info_merges_url_and_dom_metadata(self):
        page = FakePage(
            url="https://www.tiktok.com/foryou",
            dom_result={
                "video_url": "/@creator/video/7390000000000000001?share=1",
                "author_url": "/@creator",
                "author_name": "Creator Display",
                "title": "A useful caption #topic",
                "description": "A useful caption #topic",
                "raw_source": "dom_caption",
                "capture_status": "partial",
            },
        )

        info = capture_active_video_info(page)

        self.assertEqual(info["capture_status"], "ok")
        self.assertEqual(info["video_id"], "7390000000000000001")
        self.assertEqual(info["video_url"], "https://www.tiktok.com/@creator/video/7390000000000000001")
        self.assertEqual(info["author_handle"], "creator")
        self.assertEqual(info["author_name"], "Creator Display")
        self.assertEqual(info["title"], "A useful caption #topic")
        self.assertEqual(info["raw_source"], "dom_caption")
        self.assertEqual(page.evaluate_calls[0][1], [300, 600, 800])

    def test_capture_active_video_info_uses_current_url_when_dom_is_partial(self):
        page = FakePage(
            url="https://www.tiktok.com/@url_author/video/7390000000000000002",
            dom_result={
                "title": "Video from current URL",
                "raw_source": "meta_title",
            },
        )

        info = capture_active_video_info(page)

        self.assertEqual(info["capture_status"], "ok")
        self.assertEqual(info["video_id"], "7390000000000000002")
        self.assertEqual(info["author_handle"], "url_author")
        self.assertEqual(info["title"], "Video from current URL")

    def test_capture_active_video_info_returns_failed_on_page_error(self):
        page = FakePage(error=RuntimeError("page closed token=secret"))

        info = capture_active_video_info(page)

        self.assertEqual(info["capture_status"], "failed")
        self.assertEqual(info["raw_source"], "failed")
        self.assertIn("page closed", info["capture_error"])


if __name__ == "__main__":
    unittest.main()
