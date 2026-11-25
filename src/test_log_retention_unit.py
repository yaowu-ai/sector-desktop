import shutil
import os
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core import runtime
from log_retention import append_session_log


@contextmanager
def temporary_directory():
    path = Path(__file__).resolve().parent / f'.retention-test-{uuid.uuid4().hex}'
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


class LogRetentionTests(unittest.TestCase):
    def test_rotation_keeps_new_output_and_enforces_archive_budget(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'sessions.log'
            path.write_text('old\n' * 30, encoding='utf-8')
            append_session_log(path, 'new\n', max_bytes=100, archive_bytes=100)
            self.assertEqual(path.read_text(encoding='utf-8'), 'new\n')
            self.assertLessEqual(sum(p.stat().st_size for p in path.parent.glob('sessions.*.log')), 100)

    def test_expired_logs_are_removed_without_touching_unrelated_files(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'sessions.log'
            old = path.parent / 'sessions.20261101-120000-1.log'
            old.write_text('old', encoding='utf-8')
            unrelated = path.parent / 'sessions.custom.log'
            unrelated.write_text('keep', encoding='utf-8')
            append_session_log(path, 'new\n', now=datetime(2026, 11, 25, 12))
            self.assertFalse(old.exists())
            self.assertTrue(unrelated.exists())

    def test_runtime_uses_rotation_and_preserves_redaction(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'sessions.log'
            with patch.object(runtime, 'SESSION_LOG', path), patch.dict(
                'os.environ', {'AM_LOGIN_PASSWORD': 'secret-value'}
            ), patch('builtins.print'):
                runtime.session_log('password=secret-value')
            self.assertNotIn('secret-value', path.read_text(encoding='utf-8'))

    def test_busy_rotation_keeps_logging_without_failing_the_task(self):
        with temporary_directory() as directory:
            path = directory / 'sessions.log'
            path.write_text('old\n' * 30, encoding='utf-8')
            with patch.object(Path, 'rename', side_effect=PermissionError('busy')):
                append_session_log(path, 'new\n', max_bytes=100)
            self.assertTrue(path.read_text(encoding='utf-8').endswith('new\n'))

    def test_scheduler_owns_rotation_without_inheriting_a_locked_log_handle(self):
        with temporary_directory() as directory:
            path = directory / 'scheduler.log'
            path.write_text('old\n', encoding='utf-8')
            with path.open('r+b') as stream:
                stream.truncate(10 * 1024 * 1024)
            code = ('from log_retention import install_scheduler_logging; '
                    'install_scheduler_logging(); print("调度仍在运行", flush=True)')
            env = {**os.environ, 'AM_SCHEDULER_LOG_PATH': str(path)}
            child = subprocess.Popen([sys.executable, '-c', code],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                cwd=Path(__file__).resolve().parent)
            self.assertEqual(child.wait(timeout=10), 0)
            self.assertLess(path.stat().st_size, 1024)
            self.assertEqual(path.read_text(encoding='utf-8'), '调度仍在运行\n')
            self.assertTrue(list(directory.glob('scheduler.*.log')))


if __name__ == '__main__':
    unittest.main()
