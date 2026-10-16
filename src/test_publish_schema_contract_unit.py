"""Exercise Python against the *actual Rust migration*, not a parallel schema."""
import contextlib
import io
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from platforms.tiktok.publish import validate_publish_source
from platforms.tiktok.publish_store import PublishStore


ROOT = Path(__file__).resolve().parents[1]


def actual_schema():
    source = (ROOT / 'desktop/src-tauri/src/commands/publishing.rs').read_text(encoding='utf-8')
    match = re.search(r'pub const PUBLISH_SCHEMA\s*:\s*&str\s*=\s*r#"(.*?)"#;', source, re.S)
    if not match:
        raise AssertionError('Rust migration must expose its executable schema')
    return match.group(1)


class PublishingSchemaContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'local video.mp4'
        self.path.write_bytes(b'local-test-video')
        self.conn = sqlite3.connect(str(Path(self.temp.name) / 'actions.db'))
        self.addCleanup(self.conn.close)
        self.conn.executescript(actual_schema())
        stat = self.path.stat()
        self.conn.execute('INSERT INTO publish_batches VALUES (?,?,?,?,?,?,?)',
                          ('B1', 'tiktok', str(self.path.resolve()), stat.st_size,
                           str(stat.st_mtime_ns), 'caption\n#travel', '2026-10-15T00:00:00.000Z'))
        self.conn.execute('''INSERT INTO publish_records
          (id,batch_id,account_id,provider,profile_binding_json,ordinal,updated_at)
          VALUES (?,?,?,?,?,?,?)''', ('B1_0', 'B1', 'tiktok_1', 'bitbrowser', '{}', 0,
                                      '2026-10-15T00:00:00.000Z'))
        self.conn.commit()
        self.store = PublishStore(self.conn)

    def quiet(self, function, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(*args, **kwargs)

    def test_real_migration_is_repeatable_and_preserves_old_tables_and_history(self):
        self.conn.execute('CREATE TABLE IF NOT EXISTS action_log (detail TEXT)')
        self.conn.execute("INSERT INTO action_log VALUES ('existing-history')")
        self.conn.commit()
        self.conn.executescript(actual_schema())
        self.conn.executescript(actual_schema())
        self.assertEqual(self.conn.execute('SELECT detail FROM action_log').fetchone()[0], 'existing-history')
        self.assertEqual(self.store.for_account('B1', 'tiktok_1')['caption'], 'caption\n#travel')

    def test_actual_schema_metadata_is_consumed_by_uploader_and_not_copied(self):
        record = self.store.for_account('B1', 'tiktok_1')
        self.assertEqual(validate_publish_source(record), str(self.path.resolve()))
        self.path.write_bytes(b'changed video contents')
        with self.assertRaisesRegex(RuntimeError, '视频文件已变化'):
            validate_publish_source(record)
        self.assertEqual(self.store.record('B1_0')['caption'], 'caption\n#travel')

    def test_unique_account_prevents_second_attempt_in_same_batch(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute('''INSERT INTO publish_records
              (id,batch_id,account_id,provider,profile_binding_json,ordinal,updated_at)
              VALUES ('B1_1','B1','tiktok_1','ixbrowser','{}',1,'now')''')
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM publish_records').fetchone()[0], 1)

    def test_claim_and_commit_are_compare_and_set_on_real_rust_table(self):
        self.assertTrue(self.quiet(self.store.claim, 'B1_0'))
        self.assertFalse(self.quiet(self.store.claim, 'B1_0'))
        self.assertTrue(self.quiet(self.store.transition, 'B1_0', ('running',),
                                   'committing', 'submitting', submitted_at='2026-10-15T01:00:00.000Z'))
        self.assertFalse(self.quiet(self.store.transition, 'B1_0', ('running',),
                                    'committing', 'submitting'))
        self.assertEqual(self.store.record('B1_0')['submitted_at'], '2026-10-15T01:00:00.000Z')

    def test_verified_fact_cannot_be_reopened_for_republishing(self):
        self.quiet(self.store.claim, 'B1_0')
        self.quiet(self.store.transition, 'B1_0', ('running',), 'committing', 'submitting')
        self.quiet(self.store.transition, 'B1_0', ('committing',), 'verifying', 'verifying', post_id='101')
        self.quiet(self.store.transition, 'B1_0', ('verifying',), 'verified', 'finished',
                   post_url='https://www.tiktok.com/@alice/video/101')
        self.assertFalse(self.quiet(self.store.claim, 'B1_0'))
        with self.assertRaises(ValueError):
            self.quiet(self.store.transition, 'B1_0', ('verified',), 'running', 'opening')
        self.assertEqual(self.store.record('B1_0')['post_url'], 'https://www.tiktok.com/@alice/video/101')


if __name__ == '__main__':
    unittest.main()
