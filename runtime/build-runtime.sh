#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_ARCH="${PYTHON_ARCH:-}"
DIST_DIR="${DIST_DIR:-runtime/dist}"
WORK_DIR="${WORK_DIR:-build}"
COPY_TO_TAURI_RESOURCES="${COPY_TO_TAURI_RESOURCES:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SPEC="${REPO_DIR}/runtime/pyinstaller/account-matrix-runtime.spec"
DIST="${REPO_DIR}/${DIST_DIR}"
WORK="${REPO_DIR}/${WORK_DIR}"

PYTHON_CMD=("${PYTHON_BIN}")
if [[ -n "${PYTHON_ARCH}" ]]; then
  PYTHON_CMD=(arch "-${PYTHON_ARCH}" "${PYTHON_BIN}")
fi

cd "${REPO_DIR}"
"${PYTHON_CMD[@]}" -m PyInstaller --clean --noconfirm --distpath "${DIST}" --workpath "${WORK}" "${SPEC}"

RUNTIME_DIR="${DIST}/account-matrix-runtime"
"${PYTHON_CMD[@]}" runtime/runtime_manifest.py --runtime-dir "${RUNTIME_DIR}"
RUNTIME_EXE="${RUNTIME_DIR}/account-matrix-runtime"
if [[ ! -x "${RUNTIME_EXE}" ]]; then
  echo "[error] runtime executable missing or not executable: ${RUNTIME_EXE}" >&2
  exit 1
fi
if [[ "$(uname -s)" == "Darwin" && -e "${RUNTIME_DIR}/account-matrix-runtime.exe" ]]; then
  echo "[error] macOS runtime directory contains Windows executable: ${RUNTIME_DIR}/account-matrix-runtime.exe" >&2
  exit 1
fi

if ! "${PYTHON_CMD[@]}" - "${RUNTIME_DIR}/runtime-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if "profile-stats" not in manifest.get("supportedCommands", []):
    raise SystemExit("runtime manifest missing profile-stats command")
PY
then
  exit 1
fi

RUNTIME_CMD=("${RUNTIME_EXE}")
if [[ -n "${PYTHON_ARCH}" ]]; then
  RUNTIME_CMD=(arch "-${PYTHON_ARCH}" "${RUNTIME_EXE}")
fi
PROFILE_STATS_SMOKE_JSON="${RUNTIME_DIR}/profile-stats-smoke.json"
"${RUNTIME_CMD[@]}" profile-stats --json >"${PROFILE_STATS_SMOKE_JSON}"
"${PYTHON_CMD[@]}" - "${PROFILE_STATS_SMOKE_JSON}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("status") != "ok":
    raise SystemExit(f"profile-stats smoke returned {payload.get('status')!r}")
PY
rm -f "${PROFILE_STATS_SMOKE_JSON}"

if [[ "${COPY_TO_TAURI_RESOURCES}" == "1" ]]; then
  TARGET="${REPO_DIR}/desktop/src-tauri/resources/runtime"
  mkdir -p "${TARGET}"
  rsync -a --delete --exclude ".gitkeep" "${RUNTIME_DIR}/" "${TARGET}/"
  if [[ ! -x "${TARGET}/account-matrix-runtime" ]]; then
    echo "[error] Tauri runtime resource missing executable: ${TARGET}/account-matrix-runtime" >&2
    exit 1
  fi
  if [[ "$(uname -s)" == "Darwin" && -e "${TARGET}/account-matrix-runtime.exe" ]]; then
    echo "[error] Tauri runtime resource contains Windows executable on macOS" >&2
    exit 1
  fi
fi
