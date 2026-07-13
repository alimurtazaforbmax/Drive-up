#!/usr/bin/env bash
# Package dist/DriveUp into a .deb for Ubuntu 22.04 (amd64).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="1.0.0"
ARCH="amd64"
PKG_NAME="driveup"
STAGE="dist/deb/${PKG_NAME}_${VERSION}_${ARCH}"

if [[ ! -x dist/DriveUp/DriveUp ]]; then
  echo "Missing dist/DriveUp/DriveUp — run scripts/build_linux.sh first" >&2
  exit 1
fi

rm -rf dist/deb
mkdir -p \
  "${STAGE}/DEBIAN" \
  "${STAGE}/opt/driveup" \
  "${STAGE}/usr/bin" \
  "${STAGE}/usr/share/applications"

cp -a dist/DriveUp/. "${STAGE}/opt/driveup/"

cat > "${STAGE}/usr/bin/driveup" <<'EOF'
#!/bin/sh
exec /opt/driveup/DriveUp "$@"
EOF
chmod 755 "${STAGE}/usr/bin/driveup"
chmod 755 "${STAGE}/opt/driveup/DriveUp"

cat > "${STAGE}/usr/share/applications/driveup.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=DriveUp
Comment=Upload folders and files to Google Drive
Exec=driveup
Terminal=false
Categories=Utility;Network;
StartupNotify=true
EOF

cat > "${STAGE}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: DriveUp <noreply@example.com>
Depends: libc6 (>= 2.35), libgl1, libxkbcommon0, libdbus-1-3, libxcb-cursor0, libfontconfig1
Description: DriveUp — upload folders and files to Google Drive
 Desktop app for queuing folder/file uploads to Google Drive with OAuth.
EOF

mkdir -p dist/installers
DEB="dist/installers/${PKG_NAME}_${VERSION}_${ARCH}-ubuntu22.04.deb"
dpkg-deb --build --root-owner-group "${STAGE}" "${DEB}"

echo "==> Debian package ready: ${DEB}"
echo "    Install on Ubuntu 22.04: sudo apt install ./${PKG_NAME}_${VERSION}_${ARCH}-ubuntu22.04.deb"
