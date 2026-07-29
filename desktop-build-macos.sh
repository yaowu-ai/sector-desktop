#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
COPY_TO_TAURI_RESOURCES=1 PYTHON_BIN="${PYTHON_BIN}" bash ./runtime/build-runtime.sh

cd desktop
corepack pnpm tauri build
