#!/usr/bin/env bash
# Build DriveUp for macOS (.app via PyInstaller)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

echo "==> Installing build dependencies"
"$PYTHON" -m pip install -r requirements.txt -r requirements-build.txt

echo "==> Cleaning previous build"
rm -rf dist/DriveUp dist/DriveUp.app build/DriveUp

echo "==> Running PyInstaller"
"$PYTHON" -m PyInstaller --noconfirm --clean driveup.spec

if [[ -d dist/DriveUp.app ]]; then
  OUT="dist/DriveUp.app"
elif [[ -d dist/DriveUp ]]; then
  OUT="dist/DriveUp"
else
  echo "Build failed: no dist output found" >&2
  exit 1
fi

echo "==> macOS build ready: $OUT"
echo "    Optional DMG: brew install create-dmg && create-dmg dist/DriveUp.dmg $OUT"

mkdir -p dist/installers
if command -v create-dmg >/dev/null 2>&1 && [[ -d dist/DriveUp.app ]]; then
  create-dmg \
    --volname "DriveUp" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --app-drop-link 400 180 \
    "dist/installers/DriveUp-1.0.0-macOS.dmg" \
    "dist/DriveUp.app" || true
fi
