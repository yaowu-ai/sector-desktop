"""Patchright startup helpers with clearer diagnostics."""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def start_sync_playwright():
    """Start Patchright sync API and rewrite its common startup masking error."""
    _patch_patchright_driver_env()
    from patchright.sync_api import sync_playwright

    manager = sync_playwright()
    try:
        with _clean_windows_dll_directory_for_child_processes():
            playwright = manager.start()
    except Exception as exc:
        raise RuntimeError(patchright_startup_error_detail(manager, exc)) from exc
    return manager, playwright


def patchright_driver_check() -> dict[str, str]:
    """Verify that Patchright's Node driver stays alive long enough to accept protocol."""
    try:
        return _run_driver_smoke_test(timeout_seconds=2.0)
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def patchright_startup_check() -> dict[str, str]:
    """Return a JSON-safe startup health check for Patchright's driver."""
    try:
        manager, playwright = start_sync_playwright()
        try:
            browser_type = getattr(playwright, "chromium", None)
            return {
                "status": "ok",
                "detail": f"Patchright sync API started; chromium={browser_type}",
            }
        finally:
            manager.__exit__()
    except Exception as exc:
        return {
            "status": "error",
            "detail": str(exc),
        }


def patchright_startup_error_detail(manager: Any, exc: Exception) -> str:
    details = [f"{type(exc).__name__}: {exc}"]
    underlying = _driver_future_exception(manager)
    if underlying is not None:
        details.append(f"driverError={type(underlying).__name__}: {underlying}")

    try:
        from patchright._impl._driver import compute_driver_executable

        executable, entrypoint = compute_driver_executable()
        details.append(_path_detail("node", executable))
        details.append(_path_detail("cli", entrypoint))
    except Exception as driver_exc:
        details.append(f"driverPathError={type(driver_exc).__name__}: {driver_exc}")

    smoke = patchright_driver_check()
    details.append(f"driverSmoke={smoke['status']}: {smoke['detail']}")

    return "Patchright startup failed; " + "; ".join(details)


def _patch_patchright_driver_env() -> None:
    """Patch Patchright subprocess setup for the packaged Windows runtime."""
    from patchright._impl import _driver, _transport

    original_env = _driver.get_driver_env
    if not getattr(original_env, "_account_matrix_patched", False):
        def get_driver_env() -> dict:
            return _sanitize_driver_env(original_env())

        get_driver_env._account_matrix_patched = True  # type: ignore[attr-defined]
        _driver.get_driver_env = get_driver_env
        _transport.get_driver_env = get_driver_env

    original_executable = _driver.compute_driver_executable
    if getattr(original_executable, "_account_matrix_patched", False):
        return

    def compute_driver_executable() -> tuple[str, str]:
        executable, entrypoint = original_executable()
        return (
            _normalize_windows_node_path(executable),
            _normalize_windows_node_path(entrypoint),
        )

    compute_driver_executable._account_matrix_patched = True  # type: ignore[attr-defined]
    _driver.compute_driver_executable = compute_driver_executable
    _transport.compute_driver_executable = compute_driver_executable


def _sanitize_driver_env(env: dict[str, str]) -> dict[str, str]:
    cleaned = dict(env)
    for key in list(cleaned):
        upper = key.upper()
        if upper.startswith("_PYI") or upper in {
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONEXECUTABLE",
            "VIRTUAL_ENV",
        }:
            cleaned.pop(key, None)
    return cleaned


def _normalize_windows_node_path(value: str) -> str:
    """Node 24 can mis-resolve local script paths with the Windows long-path prefix."""
    if sys.platform != "win32":
        return value
    path = os.fspath(value)
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


@contextmanager
def _clean_windows_dll_directory_for_child_processes():
    """Avoid leaking PyInstaller's DLL search directory into child node.exe processes."""
    if sys.platform != "win32":
        yield
        return

    kernel32 = None
    restore_dir = getattr(sys, "_MEIPASS", None)
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetDllDirectoryW(None)
    except Exception:
        kernel32 = None

    try:
        yield
    finally:
        if kernel32 is not None and restore_dir:
            try:
                kernel32.SetDllDirectoryW(str(restore_dir))
            except Exception:
                pass


def _run_driver_smoke_test(timeout_seconds: float) -> dict[str, str]:
    _patch_patchright_driver_env()
    from patchright._impl._driver import compute_driver_executable, get_driver_env

    executable, entrypoint = compute_driver_executable()
    command = [executable, entrypoint, "run-driver"]
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    with _clean_windows_dll_directory_for_child_processes():
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_sanitize_driver_env(get_driver_env()),
            startupinfo=startupinfo,
        )

    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _stop_process(proc)
        return {
            "status": "ok",
            "detail": (
                f"driver stayed alive for {timeout_seconds:.1f}s; "
                f"{_path_detail('node', executable)}; {_path_detail('cli', entrypoint)}"
            ),
        }

    stdout, stderr = proc.communicate(timeout=1)
    detail = (
        f"driver exited early code={proc.returncode}; "
        f"stdout={_decode_output(stdout)!r}; stderr={_decode_output(stderr)!r}; "
        f"{_path_detail('node', executable)}; {_path_detail('cli', entrypoint)}"
    )
    return {"status": "error", "detail": detail}


def _stop_process(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _decode_output(value: bytes | None) -> str:
    if not value:
        return ""
    return value.decode("utf-8", errors="replace").strip()


def _driver_future_exception(manager: Any) -> Exception | None:
    connection = getattr(manager, "_connection", None)
    transport = getattr(connection, "_transport", None)
    future = getattr(transport, "on_error_future", None)
    if future is None or not future.done():
        return None
    try:
        future.result()
    except Exception as exc:
        return exc
    return None


def _path_detail(label: str, value: str) -> str:
    path = Path(value)
    if path.exists():
        size = path.stat().st_size
        return f"{label}={path} exists=true size={size}"
    return f"{label}={path} exists=false"
