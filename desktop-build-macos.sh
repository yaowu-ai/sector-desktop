#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [[ -f "${HOME}/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.cargo/env"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
BUILD_MODE="${BUILD_MODE:-production}"
case "${BUILD_MODE}" in
  test|prod|production)
    ;;
  *)
    echo "Unsupported BUILD_MODE: ${BUILD_MODE}" >&2
    exit 1
    ;;
esac

rustup target add aarch64-apple-darwin

COPY_TO_TAURI_RESOURCES=1 PYTHON_BIN="${PYTHON_BIN}" bash ./runtime/build-runtime.sh

cd desktop
if [ "${BUILD_MODE}" = "prod" ]; then
  export DESKTOP_BUILD_MODE="production"
else
  export DESKTOP_BUILD_MODE="${BUILD_MODE}"
fi
corepack pnpm tauri build --bundles dmg
