"""Bound session logs without changing the stdout consumed by the desktop."""
import re
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024
ARCHIVE_BYTES = 100 * 1024 * 1024
_LOCK = threading.RLock()
_SCHEDULER_INSTALLED = False


def append_session_log(path, text, *, now=None, max_bytes=MAX_LOG_BYTES,
                       archive_bytes=ARCHIVE_BYTES):
    path = Path(path)
    now = now or datetime.now()
    with _LOCK:
        try:
            metadata = path.stat()
        except FileNotFoundError:
            metadata = None
        if metadata and (metadata.st_size >= max_bytes or
                         datetime.fromtimestamp(metadata.st_mtime).date() < now.date()):
            # Rename uses no extra disk space, including for an oversized legacy log.
            stamp = datetime.fromtimestamp(metadata.st_mtime).strftime('%Y%m%d-%H%M%S')
            try:
                path.rename(path.with_name(f'{path.stem}.{stamp}-{time.time_ns()}.log'))
                _prune_archives(path, now, archive_bytes)
            except OSError:
                pass  # A busy log defers rotation; it must not fail the account task.
        # Include pruning on first use so upgrades also remove pre-existing archives.
        elif metadata is None:
            try:
                _prune_archives(path, now, archive_bytes)
            except OSError:
                pass
        with path.open('a', encoding='utf-8', errors='backslashreplace') as stream:
            stream.write(text)


def _prune_archives(active, now, budget):
    pattern = re.compile(rf'^{re.escape(active.stem)}\.(\d{{8}}-\d{{6}})-\d+\.log$')
    archives = []
    for path in active.parent.iterdir():
        match = pattern.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        try:
            stamp = datetime.strptime(match[1], '%Y%m%d-%H%M%S')
            archives.append((stamp, path, path.stat().st_size))
        except (ValueError, OSError):
            continue
    used = 0
    for stamp, path, size in sorted(archives, reverse=True):
        if stamp < now - timedelta(days=7) or used + size > budget:
            try:
                path.unlink()
            except OSError:
                used += size
        else:
            used += size


class SchedulerLogStream:
    encoding = 'utf-8'
    errors = 'backslashreplace'

    def __init__(self, path, descriptor):
        self.path = path
        self.descriptor = descriptor

    def write(self, text):
        try:
            append_session_log(self.path, text)
        except OSError:
            pass  # A full disk must not terminate background account tasks.
        return len(text)

    def flush(self):
        pass  # Each write opens, flushes and closes the file.

    def isatty(self):
        return False

    def fileno(self):
        return self.descriptor

    def reconfigure(self, **kwargs):
        pass


def install_scheduler_logging():
    """Own rotation inside the scheduler, which can outlive the desktop."""
    global _SCHEDULER_INSTALLED
    path = os.environ.get('AM_SCHEDULER_LOG_PATH')
    if not path or _SCHEDULER_INSTALLED:
        return
    path = Path(path)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.flush()
    sys.stdout = sys.__stdout__ = SchedulerLogStream(path, 1)
    sys.stderr = sys.__stderr__ = SchedulerLogStream(path, 2)
    _SCHEDULER_INSTALLED = True
