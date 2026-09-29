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

corepack pnpm tauri build --bundles app

APP_NAME="$(node -p "require('./src-tauri/tauri.conf.json').productName")"
APP_VERSION="$(node -p "require('./src-tauri/tauri.conf.json').version")"
APP_PATH="src-tauri/target/release/bundle/macos/${APP_NAME}.app"
DMG_DIR="src-tauri/target/release/bundle/dmg"
DMG_PATH="${DMG_DIR}/${APP_NAME}_${APP_VERSION}_aarch64.dmg"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "[error] app bundle not found: ${APP_PATH}" >&2
  exit 1
fi

mkdir -p "${DMG_DIR}"
hdiutil create -volname "${APP_NAME}" -srcfolder "${APP_PATH}" -ov -format UDZO "${DMG_PATH}"
