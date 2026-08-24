"""Regression checks for Patchright runtime cleanup."""
from __future__ import annotations

import gc
import sys
import unittest
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from patchright_runtime import stop_sync_playwright


class FakeLoop:
    def __init__(self, closed: bool):
        self.closed = closed

    def is_closed(self) -> bool:
        return self.closed


class FakeStream:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.stdin = FakeStream()
        self.stdout = FakeStream()
        self.stderr = FakeStream()

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: int | None = None) -> int:
        self.returncode = 0
        return self.returncode


class FakeTransport:
    def __init__(self, process: FakeProcess):
        self._proc = process
        self._stopped = False


class FakeConnection:
    def __init__(self, process: FakeProcess):
        self._transport = FakeTransport(process)


class PipeTransport:
    async def wait_until_stopped(self) -> None:
        return None


class FakeManager:
    def __init__(self, *, loop_closed: bool, exit_error: Exception | None = None):
        self._loop = FakeLoop(loop_closed)
        self.process = FakeProcess()
        self._connection = FakeConnection(self.process)
        self._exit_was_called = False
        self.exit_error = exit_error
        self.exit_calls = 0

    def __exit__(self) -> None:
        self.exit_calls += 1
        if self.exit_error is not None:
            PipeTransport().wait_until_stopped()
            raise self.exit_error
        self._exit_was_called = True


class PatchrightRuntimeCleanupChecks(unittest.TestCase):
    def test_normal_exit_remains_unchanged(self) -> None:
        manager = FakeManager(loop_closed=False)

        self.assertIsNone(stop_sync_playwright(manager))
        self.assertEqual(manager.exit_calls, 1)
        self.assertFalse(manager.process.terminated)

    def test_closed_loop_forces_driver_cleanup_without_calling_exit(self) -> None:
        manager = FakeManager(loop_closed=True)

        detail = stop_sync_playwright(manager)

        self.assertIn("event loop was already closed", detail or "")
        self.assertEqual(manager.exit_calls, 0)
        self.assertTrue(manager.process.terminated)
        self.assertTrue(manager.process.stdin.closed)
        self.assertTrue(manager.process.stdout.closed)
        self.assertTrue(manager.process.stderr.closed)

    def test_failed_exit_suppresses_unawaited_transport_warning(self) -> None:
        manager = FakeManager(loop_closed=False, exit_error=RuntimeError("loop stopped"))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            detail = stop_sync_playwright(manager)
            gc.collect()

        self.assertIn("RuntimeError: loop stopped", detail or "")
        self.assertTrue(manager.process.terminated)
        self.assertFalse(
            any("PipeTransport.wait_until_stopped" in str(item.message) for item in caught)
        )


if __name__ == "__main__":
    unittest.main()
