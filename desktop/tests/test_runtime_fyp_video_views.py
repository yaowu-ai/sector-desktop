import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from core import runtime


class RuntimeFypVideoViewTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        runtime.initialize_db_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_init_db_creates_fyp_video_view_schema(self):
        columns = runtime.table_columns(self.conn, "fyp_video_views")
        self.assertIn("session_id", columns)
        self.assertIn("video_index", columns)
        self.assertIn("title", columns)
        self.assertIn("liked", columns)

        indexes = {
            row[1]
            for row in self.conn.execute("PRAGMA index_list(fyp_video_views)").fetchall()
        }
        self.assertIn("idx_fyp_video_views_account_ts", indexes)
        self.assertIn("idx_fyp_video_views_video_id", indexes)

    def test_record_fyp_video_view_redacts_and_truncates_text(self):
        with patch.dict(os.environ, {"AM_TEST_TOKEN": "secret-token"}, clear=False):
            ok = runtime.record_fyp_video_view(
                self.conn,
                "tiktok",
                "acct_1",
                {
                    "session_id": "session_1",
                    "video_index": 1,
                    "video_id": "7390000000000000000",
                    "video_url": "https://www.tiktok.com/@demo/video/7390000000000000000",
                    "author_handle": "demo",
                    "author_name": "Demo Creator",
                    "title": "A" * 400,
                    "description": "token=secret-token should be redacted",
                    "watch_seconds": "4.5",
                    "capture_status": "ok",
                    "raw_source": "dom_caption",
                },
            )

        self.assertTrue(ok)
        row = self.conn.execute(
            "SELECT title, description, watch_seconds, liked, followed, commented "
            "FROM fyp_video_views WHERE account_id='acct_1'"
        ).fetchone()
        self.assertEqual(len(row[0]), 300)
        self.assertIn("token=***", row[1])
        self.assertEqual(row[2], 4.5)
        self.assertEqual(row[3:], (0, 0, 0))

    def test_update_fyp_video_interactions_updates_existing_row(self):
        self.assertTrue(
            runtime.record_fyp_video_view(
                self.conn,
                "tiktok",
                "acct_1",
                {
                    "session_id": "session_1",
                    "video_index": 2,
                    "capture_status": "partial",
                },
            )
        )

        updated = runtime.update_fyp_video_interactions(
            self.conn,
            "tiktok",
            "acct_1",
            "session_1",
            2,
            liked=True,
            commented=True,
        )

        self.assertTrue(updated)
        row = self.conn.execute(
            "SELECT liked, followed, commented FROM fyp_video_views "
            "WHERE account_id='acct_1' AND session_id='session_1' AND video_index=2"
        ).fetchone()
        self.assertEqual(row, (1, 0, 1))

    def test_record_fyp_video_view_merges_duplicate_video_id_in_same_session(self):
        first_index = runtime.record_fyp_video_view(
            self.conn,
            "tiktok",
            "acct_1",
            {
                "session_id": "session_1",
                "video_index": 1,
                "video_id": "7390000000000000000",
                "title": "Original title",
                "watch_seconds": 2,
                "capture_status": "partial",
            },
        )
        duplicate_index = runtime.record_fyp_video_view(
            self.conn,
            "tiktok",
            "acct_1",
            {
                "session_id": "session_1",
                "video_index": 3,
                "video_id": "7390000000000000000",
                "title": "Original title",
                "watch_seconds": 8,
                "liked": True,
                "capture_status": "ok",
            },
        )

        self.assertEqual(first_index, 1)
        self.assertEqual(duplicate_index, 1)
        rows = self.conn.execute(
            "SELECT video_index, video_id, title, watch_seconds, liked, capture_status "
            "FROM fyp_video_views WHERE account_id='acct_1'"
        ).fetchall()
        self.assertEqual(rows, [(1, "7390000000000000000", "Original title", 8.0, 1, "ok")])

    def test_record_fyp_video_view_merges_duplicate_title_without_video_id(self):
        runtime.record_fyp_video_view(
            self.conn,
            "tiktok",
            "acct_1",
            {
                "session_id": "session_1",
                "video_index": 1,
                "title": "(2)Watch trending videos for you | TikTok",
                "capture_status": "partial",
            },
        )
        duplicate_index = runtime.record_fyp_video_view(
            self.conn,
            "tiktok",
            "acct_1",
            {
                "session_id": "session_1",
                "video_index": 2,
                "title": "(2)Watch trending videos for you | TikTok",
                "capture_status": "partial",
            },
        )

        self.assertEqual(duplicate_index, 1)
        count = self.conn.execute("SELECT COUNT(*) FROM fyp_video_views").fetchone()[0]
        self.assertEqual(count, 1)

    def test_record_fyp_video_view_invalid_record_is_best_effort(self):
        ok = runtime.record_fyp_video_view(
            self.conn,
            "tiktok",
            "acct_1",
            {"session_id": "", "video_index": 0},
        )
        self.assertFalse(ok)
        count = self.conn.execute("SELECT COUNT(*) FROM fyp_video_views").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
