import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import runtime


class SchedulerSqliteTests(unittest.TestCase):
    def test_runtime_enables_wal_without_relaxing_durability_or_losing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actions.db"
            old = sqlite3.connect(path)
            runtime.initialize_db_schema(old)
            old.execute("INSERT INTO action_log(platform, account_id, action) VALUES ('tiktok','a','keep')")
            old.commit()
            old.close()
            with patch.object(runtime, "LOG_DB", path):
                writer = runtime.init_db()
            reader = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            try:
                self.assertEqual(writer.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(writer.execute("PRAGMA synchronous").fetchone()[0], 2)
                self.assertEqual(writer.execute("PRAGMA busy_timeout").fetchone()[0], 2000)
                reader.execute("BEGIN")
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM action_log").fetchone()[0], 1)
                writer.execute("INSERT INTO action_log(platform, action) VALUES ('tiktok','new')")
                writer.commit()  # Must succeed while the reader holds an old snapshot.
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM action_log").fetchone()[0], 1)
                reader.rollback()
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM action_log").fetchone()[0], 2)
            finally:
                reader.close()
                writer.close()

    def test_existing_scheduler_rows_are_preserved_and_time_index_serves_query(self):
        conn = sqlite3.connect(":memory:")
        try:
            runtime.initialize_db_schema(conn)
            conn.executemany(
                "INSERT INTO scheduler_job_runs(job_id,platform,account_id,status,created_at,scheduled_run,started_at) VALUES (?,?,?,?,?,?,?)",
                [("started", "tiktok", "a", "success", "2026-01-01", "2026-01-02", "2026-01-04"),
                 ("scheduled", "tiktok", "a", "failed", "2026-01-01", "2026-01-03", None),
                 ("created", "tiktok", "a", "skipped", "2026-01-02", None, None)],
            )
            conn.commit()
            runtime.initialize_db_schema(conn)
            query = "SELECT job_id FROM scheduler_job_runs WHERE platform=? AND COALESCE(started_at, scheduled_run, created_at)>=? ORDER BY COALESCE(started_at, scheduled_run, created_at) DESC, job_id DESC LIMIT ?"
            self.assertEqual([r[0] for r in conn.execute(query, ("tiktok", "2026-01-01", 120))],
                             ["started", "scheduled", "created"])
            plan = " ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + query, ("tiktok", "2026-01-01", 120)))
            self.assertIn("idx_scheduler_runs_platform_time", plan)
            self.assertNotIn("TEMP B-TREE", plan)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
