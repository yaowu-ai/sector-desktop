# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
import patchright

ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"
INS_SRC = ROOT.parent / "account-matrix-ins" / "src"
PATCHRIGHT_DIR = Path(patchright.__file__).resolve().parent
PATCHRIGHT_DRIVER_DIR = PATCHRIGHT_DIR / "driver"
PATCHRIGHT_DATAS = []
if PATCHRIGHT_DRIVER_DIR.exists():
    PATCHRIGHT_DATAS.append((str(PATCHRIGHT_DRIVER_DIR), "patchright/driver"))

LOCAL_HIDDENIMPORTS = [
    "actions",
    "ai_comment",
    "bitbrowser",
    "gmail_setup",
    "human_mouse",
    "main",
    "notify",
    "patchright_runtime",
    "platform_config",
    "runtime_config",
    "scheduler",
    "stats",
    "sync_accounts_config",
    "target_engage",
    "test_comment",
    "test_like",
]

a = Analysis(
    [str(SRC / "runtime_cli.py")],
    pathex=[str(SRC), str(INS_SRC)] if INS_SRC.exists() else [str(SRC)],
    binaries=[],
    datas=PATCHRIGHT_DATAS,
    hiddenimports=LOCAL_HIDDENIMPORTS
    + collect_submodules("core")
    + collect_submodules("platforms")
    + (collect_submodules("ins") if INS_SRC.exists() else [])
    + collect_submodules("patchright")
    + [
        "apscheduler.schedulers.asyncio",
        "fastapi",
        "patchright.sync_api",
        "requests",
        "uvicorn",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "desktop",
        "docs",
        "tests",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="account-matrix-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="account-matrix-runtime",
)
