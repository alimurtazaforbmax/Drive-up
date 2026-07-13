# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DriveUp (Windows / macOS / Linux)."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "assets" / "fonts" / "PlusJakartaSans.ttf"), "assets/fonts"),
]

hiddenimports = [
    "google.auth",
    "google.auth.transport.requests",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.http",
    "platformdirs",
    "watchdog",
    "watchdog.observers",
    "watchdog.events",
]

tmp_ret = collect_all("PyQt6")
datas += tmp_ret[0]
binaries = list(tmp_ret[1])
hiddenimports += tmp_ret[2]
datas += collect_data_files("googleapiclient")

ico = ROOT / "assets" / "icons" / "driveup.ico"
icns = ROOT / "assets" / "icons" / "driveup.icns"
exe_kwargs = {}
if ico.is_file():
    exe_kwargs["icon"] = str(ico)

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DriveUp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **exe_kwargs,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DriveUp",
)

if sys.platform == "darwin":
    bundle_kwargs = {
        "name": "DriveUp.app",
        "bundle_identifier": "com.googledriveproject.driveup",
        "info_plist": {
            "CFBundleName": "DriveUp",
            "CFBundleDisplayName": "DriveUp",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    }
    if icns.is_file():
        bundle_kwargs["icon"] = str(icns)
    app = BUNDLE(coll, **bundle_kwargs)
