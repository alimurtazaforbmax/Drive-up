# Packaging & installers

DriveUp can be packaged for **Windows**, **macOS**, and **Linux**.  
Each OS build must be produced on that OS (or via GitHub Actions).

## Quick start (this machine)

### Windows (portable app)

```powershell
.\scripts\build_windows.ps1
```

Output: `dist\DriveUp\DriveUp.exe` — zip that folder to share a portable build.

### Windows (Setup installer)

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. Run:

```powershell
.\scripts\build_windows.ps1 -MakeInstaller
```

Output: `dist\installers\DriveUp-Setup-1.0.0-Windows.exe`

### macOS

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Output: `dist/DriveUp.app` (and a DMG if `create-dmg` is installed)

### Linux

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Output: `dist/DriveUp/` and `dist/installers/DriveUp-1.0.0-linux-x86_64.tar.gz`

## GitHub Actions (all platforms)

Push a tag or run the workflow manually:

- Workflow: `.github/workflows/build-installers.yml`
- Downloads zip/tar artifacts for Windows, macOS, and Linux from the Actions run

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Notes

- OAuth client JSON and login tokens live in the **user config directory** (not inside Program Files), so installs work without admin write access.
- Bundled font is packaged from `assets/fonts/`.
- Optional app icons: place `assets/icons/driveup.ico` (Windows) and `assets/icons/driveup.icns` (macOS).
- First run still uses **Connect** → browser Google sign-in (localhost redirect).
