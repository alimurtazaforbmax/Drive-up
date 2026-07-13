# Google Drive Folder Uploader

Cross-platform **PyQt6** desktop app that uploads any number of local folders to Google Drive, mirrors folder structure, skips duplicates by **name + size**, and optionally **watches folders** for continuous sync.

Works on **Windows, macOS, and Linux** (`pathlib` for all paths).

## Features

- OAuth sign-in with your Google account
- Queue **N folders** from anywhere on the machine
- Recreate nested folders on Drive under a chosen parent
- **Conflict resolution:** skip when same name + size exists; **update** Drive file when same name but size changed (needed for continuous sync)
- **Continuous sync:** watch queued folders; new/changed files upload automatically (debounced)
- Background uploads with progress, cancel, and retry failed
- Skips common junk (`.DS_Store`, `Thumbs.db`, `__pycache__`, etc.)

## Setup

### 1. Python environment

```bash
cd "Google Drive Project"
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the app

```bash
python src/main.py
```

### 3. Connect Google (first time)

Click **Connect Google**. DriveUp uses the modern **localhost redirect** desktop OAuth flow (not copy/paste codes):

1. Enable **Google Drive API** and create a **Desktop** OAuth client (dialog buttons open the Console pages)
2. **Import JSON** once — the app ID file from Google Cloud (not your password)
3. Browser opens → you log in → click **Allow**
4. Google redirects to `http://127.0.0.1:PORT` on your machine
5. The app receives the authorization code automatically, exchanges it for tokens, and saves the refresh token

You never copy an authorization code. Device Authorization Grant is not used (that flow is for TVs/consoles).

If the OAuth consent screen is in Testing mode, add your Google account as a test user.

Optional: you can still place a file at `credentials/client_secret.json`; the app checks that location too.

## Usage

1. Click **Connect Google**
2. Optionally **Choose Drive Folder** (default: My Drive root)
3. **Add Folder** for each local folder (repeat for N folders)
4. Click **Start Upload**
5. Optional: enable **Continuous sync** or click **Start Watching** so new/changed files keep uploading

Each local root becomes a folder with the same name under the Drive destination; subfolders are mirrored.

## Installers (Windows / macOS / Linux)

See [PACKAGING.md](PACKAGING.md) for full details.

```powershell
# Windows portable app
.\scripts\build_windows.ps1

# Windows Setup.exe (needs Inno Setup 6)
.\scripts\build_windows.ps1 -MakeInstaller
```

```bash
# macOS
./scripts/build_macos.sh

# Linux
./scripts/build_linux.sh
```

Or push a `v*` tag to run `.github/workflows/build-installers.yml` and download artifacts for all three platforms.

## Project layout

```text
credentials/client_secret.json   # you provide (gitignored)
src/
  main.py
  app.py
  auth/google_auth.py
  drive/drive_service.py
  upload/
    folder_walker.py
    folder_watcher.py
    queue_model.py
    upload_worker.py
  ui/main_window.py
  config/settings.py
```

## Notes

- Scope used: `drive.file` (files/folders created by this app)
- Large files use resumable uploads
- Watching uses the cross-platform `watchdog` library
- Disconnect deletes the local token file
