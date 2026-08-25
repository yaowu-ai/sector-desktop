#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ -f "${HOME}/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.cargo/env"
fi

PYTHON_BIN="${PYTHON_BIN:-${SCRIPT_DIR}/.runtime-build-venv-x64/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  RESOLVED_PYTHON_BIN="$(command -v "${PYTHON_BIN}" || true)"
  if [[ -z "${RESOLVED_PYTHON_BIN}" || ! -x "${RESOLVED_PYTHON_BIN}" ]]; then
    echo "[error] Intel Python not found: ${PYTHON_BIN}" >&2
    exit 1
  fi
  PYTHON_BIN="${RESOLVED_PYTHON_BIN}"
fi

PYTHON_MACHINE="$(arch -x86_64 "${PYTHON_BIN}" -c 'import platform; print(platform.machine())')"
if [[ "${PYTHON_MACHINE}" != "x86_64" ]]; then
  echo "[error] Python did not start as x86_64: ${PYTHON_MACHINE}" >&2
  exit 1
fi

rustup target add x86_64-apple-darwin

COPY_TO_TAURI_RESOURCES=1 \
PYTHON_ARCH=x86_64 \
PYTHON_BIN="${PYTHON_BIN}" \
DIST_DIR=runtime/dist-x64 \
WORK_DIR=build-x64 \
bash ./runtime/build-runtime.sh

RUNTIME="${SCRIPT_DIR}/runtime/dist-x64/account-matrix-runtime/account-matrix-runtime"
if ! file "${RUNTIME}" | grep -q "x86_64"; then
  echo "[error] bundled runtime is not x86_64: ${RUNTIME}" >&2
  file "${RUNTIME}" >&2
  exit 1
fi

arch -x86_64 "${RUNTIME}" version --json

cd desktop
corepack pnpm tauri build --target x86_64-apple-darwin --bundles dmg
