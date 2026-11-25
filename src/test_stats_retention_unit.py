import re
import sqlite3
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import stats
from test_log_retention_unit import temporary_directory


class StatsRetentionTests(unittest.TestCase):
    def test_archive_preserves_cli_counts_target_failures_and_precise_since(self):
        source = (Path(__file__).resolve().parents[1] /
                  'desktop/src-tauri/src/retention.rs').read_text(encoding='utf-8')
        schema = re.search(r'const ARCHIVE_SCHEMA: &str = "(.*?)";', source, re.S)[1]
        with temporary_directory() as directory:
            path = directory / 'actions.db'
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.executescript('''
                    CREATE TABLE action_log(id INTEGER PRIMARY KEY,account_id TEXT,action TEXT,status TEXT,detail TEXT,ts TEXT);
                    INSERT INTO action_log VALUES
                        (1,'a','fyp_browse','ok','videos=12','2026-10-01T12:00:00.001'),
                        (2,'a','like','ok','count=4','2026-10-01T12:00:01.001'),
                        (3,'a','like','fail','count=3','2026-10-01T12:00:02.001'),
                        (4,'a','target_like','fail','handle=brand reason=failed','2026-10-01T12:00:03.001');
                    CREATE TABLE target_engagements(our_account TEXT,handle TEXT,liked INTEGER,commented INTEGER,ts TEXT);
                    CREATE TABLE target_follows(our_account TEXT,handle TEXT,followed INTEGER,ts TEXT);
                ''')
                conn.execute(schema)
            with patch.object(stats, 'LOG_DB', path):
                boundary = datetime.fromisoformat('2026-10-01T12:00:00.500')
                before = (stats.aggregate(), stats.aggregate(boundary), stats.aggregate_target())
                with closing(sqlite3.connect(path)) as conn, conn:
                    conn.executescript('''
                        INSERT INTO action_stats_archive VALUES
                            ('tiktok','a','2026-10-01T12:00:00.001',1,'',1,12),
                            ('tiktok','a','2026-10-01T12:00:01.001',4,'',1,4),
                            ('tiktok','a','2026-10-01T12:00:02.001',7,'',1,3),
                            ('tiktok','a','2026-10-01T12:00:03.001',8,'brand',1,0);
                        DELETE FROM action_log;
                    ''')
                self.assertEqual(before, (stats.aggregate(), stats.aggregate(boundary), stats.aggregate_target()))


if __name__ == '__main__':
    unittest.main()
