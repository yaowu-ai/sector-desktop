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

if [[ "${COPY_TO_TAURI_RESOURCES}" == "1" ]]; then
  TARGET="${REPO_DIR}/desktop/src-tauri/resources/runtime"
  mkdir -p "${TARGET}"
  rsync -a --delete --exclude ".gitkeep" "${RUNTIME_DIR}/" "${TARGET}/"
fi
