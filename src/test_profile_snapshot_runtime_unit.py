import json
import sqlite3
import unittest

from core.runtime import initialize_db_schema, save_profile_snapshot


class ProfileSnapshotRuntimeTests(unittest.TestCase):
    def test_initialize_db_schema_creates_profile_snapshot_table(self):
        conn = sqlite3.connect(":memory:")
        try:
            initialize_db_schema(conn)
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(profile_stats_snapshots)")
            }
        finally:
            conn.close()

        self.assertIn("account_id", columns)
        self.assertIn("task_run_id", columns)
        self.assertIn("activity_matches_json", columns)
        self.assertIn("result_json", columns)

    def test_save_profile_snapshot_persists_query_columns_and_json(self):
        conn = sqlite3.connect(":memory:")
        try:
            initialize_db_schema(conn)
            snapshot_id = save_profile_snapshot(
                conn,
                {
                    "account_id": "acc-1",
                    "platform": "tiktok",
                    "status": "success",
                    "handle": "my_account",
                    "following": 1,
                    "followers": 2,
                    "likes": 3,
                    "raw": {
                        "following": "1",
                        "followers": "2",
                        "likes": "3",
                    },
                    "approximate_fields": ["followers"],
                    "liked": 4,
                    "liked_loaded": 4,
                    "liked_complete": True,
                    "liked_status": "complete",
                    "activity": {
                        "has_liked_your_comment": False,
                        "comment_like_notifications_count": 0,
                        "notifications_scanned": 5,
                        "status": "loaded_list_stable",
                        "scope": "loaded_notifications",
                        "complete": False,
                        "comment_publish_evidence": "not_confirmed",
                        "matches": [],
                    },
                    "collected_at": "2026-09-10T07:08:30+00:00",
                },
                task_run_id="task-1",
            )
            row = conn.execute(
                """
                SELECT id, platform, account_id, task_run_id, handle,
                       following, followers, likes,
                       raw_following, raw_followers, raw_likes,
                       approximate_fields_json,
                       liked, liked_loaded, liked_complete, liked_status,
                       activity_has_liked_your_comment,
                       activity_comment_like_notifications_count,
                       activity_notifications_scanned,
                       activity_complete, comment_publish_evidence,
                       status, error, result_json
                FROM profile_stats_snapshots
                WHERE id=?
                """,
                (snapshot_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row[1:11], (
            "tiktok",
            "acc-1",
            "task-1",
            "my_account",
            1,
            2,
            3,
            "1",
            "2",
            "3",
        ))
        self.assertEqual(json.loads(row[11]), ["followers"])
        self.assertEqual(row[12:22], (
            4,
            4,
            1,
            "complete",
            0,
            0,
            5,
            0,
            "not_confirmed",
            "success",
        ))
        self.assertIsNone(row[22])
        self.assertEqual(json.loads(row[23])["handle"], "my_account")

    def test_save_failed_snapshot_preserves_unknowns_as_null(self):
        conn = sqlite3.connect(":memory:")
        try:
            initialize_db_schema(conn)
            snapshot_id = save_profile_snapshot(
                conn,
                {
                    "account_id": "acc-1",
                    "platform": "tiktok",
                    "status": "failed",
                    "error": "RuntimeError: timeout",
                    "collected_at": "2026-09-10T07:08:30+00:00",
                },
            )
            row = conn.execute(
                """
                SELECT following, followers, likes, liked, liked_complete,
                       status, error
                FROM profile_stats_snapshots
                WHERE id=?
                """,
                (snapshot_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row, (
            None,
            None,
            None,
            None,
            None,
            "failed",
            "RuntimeError: timeout",
        ))


if __name__ == "__main__":
    unittest.main()
