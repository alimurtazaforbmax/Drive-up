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

**Important:** An app built on Apple Silicon will not open on Intel Macs (and vice versa).  
Use GitHub Actions artifacts:

- **DriveUp-macOS-Intel** — 2017+ Intel Macs (macOS Ventura 13+)
- **DriveUp-macOS-AppleSilicon** — M1/M2/M3 Macs

### Linux (Ubuntu 22.04)

Prefer building on **Ubuntu 22.04** (or use the CI artifact) so glibc matches:

```bash
chmod +x scripts/build_linux.sh scripts/package_linux_deb.sh
./scripts/build_linux.sh
```

Outputs:

- `dist/installers/DriveUp-1.0.0-linux-x86_64-ubuntu22.04.tar.gz`
- `dist/installers/driveup_1.0.0_amd64-ubuntu22.04.deb` (if `dpkg-deb` is available)

Install the `.deb` on Ubuntu 22.04:

```bash
sudo apt install ./driveup_1.0.0_amd64-ubuntu22.04.deb
driveup
```

Or portable:

```bash
tar -xzf DriveUp-1.0.0-linux-x86_64-ubuntu22.04.tar.gz
cd DriveUp && ./DriveUp
```

## GitHub Actions (all platforms)

Push to `master` / `main`, push a `v*` tag, or run **Build installers** manually:

- Workflow: `.github/workflows/build-installers.yml`
- Artifacts from each run:
  - `DriveUp-Windows`
  - `DriveUp-macOS-Intel` ← use this on Intel MacBook Pro
  - `DriveUp-macOS-AppleSilicon`
  - `DriveUp-Linux-Ubuntu-22.04` (`.tar.gz` + `.deb`)

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Notes

- OAuth client JSON and login tokens live in the **user config directory** (not inside Program Files), so installs work without admin write access.
- Bundled font is packaged from `assets/fonts/`.
- Optional app icons: place `assets/icons/driveup.ico` (Windows) and `assets/icons/driveup.icns` (macOS).
- First run still uses **Connect** → browser Google sign-in (localhost redirect).
- Unsigned macOS apps: first open with **Right-click → Open** if Gatekeeper blocks them.
