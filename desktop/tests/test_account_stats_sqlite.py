"""Execute the production Rust SQL against SQLite when checking collection semantics."""
import re
import sqlite3
import unittest
from pathlib import Path


class AccountStatsSqliteTests(unittest.TestCase):
    def test_production_query_uses_latest_metrics_and_any_historical_success(self):
        source = (Path(__file__).resolve().parents[1] / 'src-tauri/src/commands/account_stats.rs').read_text(encoding='utf-8')
        sql = re.search(r'conn.prepare\(\s*"(SELECT s\.account_id,.*?)"\s*\)', source, re.S).group(1)
        with sqlite3.connect(':memory:') as conn:
            conn.executescript('''
                CREATE TABLE profile_stats_snapshots (
                    id INTEGER PRIMARY KEY, platform TEXT, account_id TEXT, following INTEGER,
                    followers INTEGER, liked INTEGER, likes INTEGER, comment_publish_evidence TEXT,
                    activity_has_liked_your_comment INTEGER, status TEXT);
                INSERT INTO profile_stats_snapshots VALUES
                    (1,'tiktok','a',10,20,30,40,NULL,0,'success'),
                    (2,'tiktok','a',NULL,NULL,NULL,NULL,NULL,0,'failed'),
                    (3,'tiktok','b',2,0,3807,3,'observed',0,'success'),
                    (4,'tiktok','b',2,0,3807,3,NULL,1,'success'),
                    (5,'instagram','a',9,9,9,9,NULL,1,'success');
            ''')
            rows = {row[0]: row for row in conn.execute(sql, ('tiktok',))}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows['a'][1], 1)  # historical success survives later failure
        self.assertEqual(rows['a'][2:6], (None, None, None, None))
        self.assertEqual(rows['b'][1:6], (1, 2, 0, 3807, 3))
        self.assertEqual(rows['b'][6:], (None, 1))


if __name__ == '__main__':
    unittest.main()
