#!/usr/bin/env bash
# Build DriveUp for Linux (PyInstaller folder + optional AppImage hints)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${ROOT}/.venv-linux/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${ROOT}/venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

echo "==> Installing build dependencies"
"$PYTHON" -m pip install -r requirements.txt -r requirements-build.txt

echo "==> Cleaning previous build"
rm -rf dist/DriveUp build/DriveUp

echo "==> Running PyInstaller"
"$PYTHON" -m PyInstaller --noconfirm --clean driveup.spec

if [[ ! -x dist/DriveUp/DriveUp ]]; then
  echo "Build failed: dist/DriveUp/DriveUp not found" >&2
  exit 1
fi

mkdir -p dist/installers
ARCHIVE="dist/installers/DriveUp-1.0.0-linux-x86_64-ubuntu22.04.tar.gz"
tar -C dist -czf "$ARCHIVE" DriveUp

cat > dist/DriveUp/DriveUp.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=DriveUp
Comment=Upload folders and files to Google Drive
Exec=DriveUp
Icon=driveup
Terminal=false
Categories=Utility;Network;
EOF

echo "==> Linux build ready: dist/DriveUp"
echo "    Archive: $ARCHIVE"

if command -v dpkg-deb >/dev/null 2>&1; then
  bash "${ROOT}/scripts/package_linux_deb.sh"
else
  echo "    Tip: install dpkg-deb to also produce a .deb for Ubuntu 22.04"
fi
