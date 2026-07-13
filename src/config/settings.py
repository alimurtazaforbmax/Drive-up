"""Application paths and settings (cross-platform via platformdirs)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from src.config.paths import app_root

APP_NAME = "GoogleDriveFolderUploader"
APP_AUTHOR = "GoogleDriveProject"
APP_DISPLAY_NAME = "DriveUp"

SCOPES = ("https://www.googleapis.com/auth/drive.file",)

DEFAULT_SKIP_NAMES = frozenset(
    {
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        ".TemporaryItems",
        "__pycache__",
        ".git",
        ".svn",
        "node_modules",
    }
)

DEFAULT_SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".tmp", "~"})


@dataclass(frozen=True)
class AppSettings:
    """Resolved filesystem locations for credentials and tokens."""

    project_root: Path
    credentials_dir: Path
    project_client_secret_path: Path
    config_dir: Path
    client_secret_path: Path
    token_path: Path  # legacy single-token path (migrated on load)
    accounts_index_path: Path
    tokens_dir: Path
    data_dir: Path

    @classmethod
    def create(cls, project_root: Path | None = None) -> AppSettings:
        root = project_root or app_root()
        # Prefer user config for secrets so installers don't need write permission
        # next to Program Files; still allow a project/sidecar credentials folder.
        credentials_dir = root / "credentials"
        config_dir = Path(user_config_dir(APP_NAME, APP_AUTHOR))
        data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        tokens_dir = config_dir / "tokens"
        config_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        tokens_dir.mkdir(parents=True, exist_ok=True)
        try:
            credentials_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Installed under Program Files may be read-only — UI import still works.
            pass
        return cls(
            project_root=root,
            credentials_dir=credentials_dir,
            project_client_secret_path=credentials_dir / "client_secret.json",
            config_dir=config_dir,
            client_secret_path=config_dir / "client_secret.json",
            token_path=config_dir / "token.json",
            accounts_index_path=config_dir / "accounts.json",
            tokens_dir=tokens_dir,
            data_dir=data_dir,
        )


_settings: AppSettings | None = None


def get_settings(project_root: Path | None = None) -> AppSettings:
    """Return a process-wide AppSettings singleton."""
    global _settings
    if _settings is None or project_root is not None:
        _settings = AppSettings.create(project_root)
    return _settings
