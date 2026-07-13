"""Google OAuth 2.0 desktop flow with multi-account token persistence."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config.settings import SCOPES, AppSettings, get_settings

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    """Raised when authentication cannot be completed."""


class MissingClientSecretError(GoogleAuthError):
    """OAuth client JSON has not been imported yet."""


@dataclass
class ConnectedAccount:
    """One signed-in Google account and its upload destination."""

    id: str
    email: str
    display_name: str
    token_file: str
    destination_id: str = "root"
    destination_name: str = "My Drive"

    def label(self) -> str:
        if self.email:
            return self.email
        return self.display_name or self.id


@dataclass
class AccountsIndex:
    active_id: str | None = None
    accounts: list[ConnectedAccount] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_id": self.active_id,
            "accounts": [asdict(account) for account in self.accounts],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AccountsIndex:
        accounts: list[ConnectedAccount] = []
        for entry in raw.get("accounts") or []:
            if not isinstance(entry, dict):
                continue
            accounts.append(
                ConnectedAccount(
                    id=str(entry.get("id") or ""),
                    email=str(entry.get("email") or ""),
                    display_name=str(entry.get("display_name") or ""),
                    token_file=str(entry.get("token_file") or ""),
                    destination_id=str(entry.get("destination_id") or "root"),
                    destination_name=str(entry.get("destination_name") or "My Drive"),
                )
            )
        return cls(active_id=raw.get("active_id"), accounts=accounts)


class GoogleAuth:
    """Manage multi-account OAuth credentials and Drive API clients."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._credentials: Credentials | None = None
        self._index = self._load_index()
        self._migrate_legacy_token()

    @property
    def is_authenticated(self) -> bool:
        return self.active_account() is not None and self._has_valid_active_creds()

    def resolve_client_secret_path(self) -> Path | None:
        candidates = (
            self._settings.client_secret_path,
            self._settings.project_client_secret_path,
        )
        for path in candidates:
            if path.is_file():
                return path
        return None

    def has_client_secret(self) -> bool:
        return self.resolve_client_secret_path() is not None

    def import_client_secret(self, source_path: Path) -> Path:
        source = source_path.expanduser()
        try:
            source = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise GoogleAuthError(f"Cannot read credentials file: {exc}") from exc

        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GoogleAuthError(
                "That file is not valid JSON. Download the OAuth client JSON "
                "from Google Cloud Console (Desktop app)."
            ) from exc

        client_block = raw.get("installed") or raw.get("web")
        if not isinstance(client_block, dict):
            raise GoogleAuthError(
                "This JSON is not a Google OAuth client file. "
                "Create Credentials → OAuth client ID → Desktop app."
            )
        if not client_block.get("client_id"):
            raise GoogleAuthError("OAuth client JSON is missing client_id.")

        destination = self._settings.client_secret_path
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as exc:
            raise GoogleAuthError(f"Could not save credentials: {exc}") from exc
        return destination

    def list_accounts(self) -> list[ConnectedAccount]:
        return list(self._index.accounts)

    def active_account(self) -> ConnectedAccount | None:
        if not self._index.active_id:
            return self._index.accounts[0] if self._index.accounts else None
        for account in self._index.accounts:
            if account.id == self._index.active_id:
                return account
        return self._index.accounts[0] if self._index.accounts else None

    def set_active_account(self, account_id: str) -> ConnectedAccount:
        for account in self._index.accounts:
            if account.id == account_id:
                self._index.active_id = account_id
                self._credentials = None
                self._save_index()
                return account
        raise GoogleAuthError(f"Unknown account: {account_id}")

    def update_active_destination(self, destination_id: str, destination_name: str) -> None:
        account = self.active_account()
        if account is None:
            return
        account.destination_id = destination_id
        account.destination_name = destination_name
        self._save_index()

    def authenticate(self, *, add_account: bool = False) -> Credentials:
        """
        Sign in via browser localhost redirect.

        If add_account is True (or no accounts yet), runs OAuth and stores a
        new/updated account entry so multiple Google Drives can be switched.
        """
        if not add_account and self.active_account() is not None:
            return self.get_credentials()

        secret_path = self.resolve_client_secret_path()
        if secret_path is None:
            raise MissingClientSecretError(
                "Google app credentials are not set up yet. "
                "Import your Desktop OAuth client JSON once, then sign in."
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secret_path),
                scopes=list(SCOPES),
            )
            # select_account lets the user pick another Google identity
            creds = flow.run_local_server(
                host="localhost",
                bind_addr="127.0.0.1",
                port=0,
                open_browser=True,
                prompt="consent select_account",
                access_type="offline",
                authorization_prompt_message=(
                    "Opening your browser to sign in with Google.\n"
                    "Pick the account for this Drive, then click Allow.\n"
                    "You do not need to copy any code.\n"
                    "If the browser does not open, visit:\n{url}\n"
                ),
                success_message=(
                    "DriveUp is connected. You can close this browser tab "
                    "and return to the app."
                ),
            )
        except Exception as exc:
            raise GoogleAuthError(f"Google sign-in failed: {exc}") from exc

        email, display_name = self._fetch_profile(creds)
        account_id = self._account_id_for_email(email or display_name or "user")
        token_name = f"{account_id}.json"
        token_path = self._settings.tokens_dir / token_name
        self._write_credentials(token_path, creds)

        existing = next((a for a in self._index.accounts if a.id == account_id), None)
        if existing:
            existing.email = email or existing.email
            existing.display_name = display_name or existing.display_name
            existing.token_file = token_name
        else:
            self._index.accounts.append(
                ConnectedAccount(
                    id=account_id,
                    email=email,
                    display_name=display_name,
                    token_file=token_name,
                )
            )
        self._index.active_id = account_id
        self._credentials = creds
        self._save_index()
        return creds

    def get_credentials(self) -> Credentials:
        account = self.active_account()
        if account is None:
            return self.authenticate(add_account=True)

        creds = self._credentials or self._load_account_token(account)
        if creds and creds.valid:
            self._credentials = creds
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._credentials = creds
                self._write_credentials(self._token_path(account), creds)
                return creds
            except RefreshError as exc:
                logger.warning("Token refresh failed for %s: %s", account.label(), exc)
                self.disconnect_account(account.id)
                raise GoogleAuthError(
                    f"Session expired for {account.label()}. Please connect again."
                ) from exc

        raise GoogleAuthError(
            f"No valid login for {account.label()}. Click Connect / Add account."
        )

    def disconnect(self) -> None:
        """Disconnect the active account."""
        account = self.active_account()
        if account is None:
            self._credentials = None
            return
        self.disconnect_account(account.id)

    def disconnect_account(self, account_id: str) -> None:
        remaining: list[ConnectedAccount] = []
        removed: ConnectedAccount | None = None
        for account in self._index.accounts:
            if account.id == account_id:
                removed = account
            else:
                remaining.append(account)
        if removed is None:
            return
        token_path = self._token_path(removed)
        try:
            if token_path.exists():
                token_path.unlink()
        except OSError as exc:
            logger.warning("Could not delete token file: %s", exc)

        self._index.accounts = remaining
        if self._index.active_id == account_id:
            self._index.active_id = remaining[0].id if remaining else None
            self._credentials = None
        self._save_index()

    def build_drive_service(self) -> Any:
        credentials = self.get_credentials()
        try:
            return build("drive", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise GoogleAuthError(f"Failed to build Drive service: {exc}") from exc

    def _has_valid_active_creds(self) -> bool:
        account = self.active_account()
        if account is None:
            return False
        try:
            creds = self._credentials or self._load_account_token(account)
            if creds and creds.valid:
                self._credentials = creds
                return True
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._credentials = creds
                self._write_credentials(self._token_path(account), creds)
                return True
        except Exception as exc:
            logger.warning("Active account not usable: %s", exc)
        return False

    def _token_path(self, account: ConnectedAccount) -> Path:
        return self._settings.tokens_dir / account.token_file

    def _load_account_token(self, account: ConnectedAccount) -> Credentials | None:
        path = self._token_path(account)
        if not path.is_file():
            return None
        try:
            return Credentials.from_authorized_user_file(str(path), scopes=list(SCOPES))
        except (OSError, ValueError) as exc:
            logger.warning("Could not load token for %s: %s", account.label(), exc)
            return None

    def _write_credentials(self, path: Path, credentials: Credentials) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(credentials.to_json(), encoding="utf-8")
        except OSError as exc:
            raise GoogleAuthError(f"Could not save sign-in token: {exc}") from exc

    def _load_index(self) -> AccountsIndex:
        path = self._settings.accounts_index_path
        if not path.is_file():
            return AccountsIndex()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return AccountsIndex.from_dict(raw)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Could not read accounts index: %s", exc)
        return AccountsIndex()

    def _save_index(self) -> None:
        path = self._settings.accounts_index_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._index.to_dict(), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise GoogleAuthError(f"Could not save accounts index: {exc}") from exc

    def _migrate_legacy_token(self) -> None:
        """Import old single token.json into the multi-account index once."""
        legacy = self._settings.token_path
        if self._index.accounts or not legacy.is_file():
            return
        try:
            creds = Credentials.from_authorized_user_file(
                str(legacy),
                scopes=list(SCOPES),
            )
        except (OSError, ValueError) as exc:
            logger.warning("Legacy token unreadable: %s", exc)
            return
        email, display_name = self._fetch_profile(creds)
        account_id = self._account_id_for_email(email or "legacy")
        token_name = f"{account_id}.json"
        token_path = self._settings.tokens_dir / token_name
        self._write_credentials(token_path, creds)
        self._index.accounts.append(
            ConnectedAccount(
                id=account_id,
                email=email,
                display_name=display_name,
                token_file=token_name,
            )
        )
        self._index.active_id = account_id
        self._save_index()
        try:
            legacy.unlink()
        except OSError:
            pass

    def _account_id_for_email(self, email: str) -> str:
        digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
        return digest[:16]

    def _fetch_profile(self, credentials: Credentials) -> tuple[str, str]:
        try:
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)
            about = service.about().get(fields="user(displayName,emailAddress)").execute()
            user = about.get("user") or {}
            return (
                str(user.get("emailAddress") or "").strip(),
                str(user.get("displayName") or "").strip(),
            )
        except (HttpError, Exception) as exc:
            logger.warning("Could not resolve Google profile: %s", exc)
            return "", ""
