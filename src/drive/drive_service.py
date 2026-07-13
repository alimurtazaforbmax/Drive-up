"""Google Drive API helpers: folders, conflict skip, resumable uploads."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
RESUMABLE_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5 MiB


class DriveServiceError(Exception):
    """Raised when a Drive API operation fails."""


class DriveService:
    """Thin wrapper around the Drive API v3 service."""

    def __init__(self, service: Any) -> None:
        self._service = service
        # Cache: (parent_id, folder_name) -> folder_id
        self._folder_cache: dict[tuple[str, str], str] = {}

    def get_account_label(self) -> str:
        """Return a short account label (email or display name) when available."""
        try:
            about = (
                self._service.about()
                .get(fields="user(displayName,emailAddress)")
                .execute()
            )
        except HttpError as exc:
            logger.warning("Could not fetch Drive account info: %s", exc)
            return "Google Drive"
        user = about.get("user") or {}
        email = (user.get("emailAddress") or "").strip()
        name = (user.get("displayName") or "").strip()
        if email:
            return email
        if name:
            return name
        return "Google Drive"

    def list_folders(
        self,
        parent_id: str = "root",
        page_size: int = 100,
        query_extra: str = "",
    ) -> list[dict[str, str]]:
        """List folders under a parent (default: My Drive root)."""
        q_parts = [
            f"'{parent_id}' in parents",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false",
        ]
        if query_extra.strip():
            escaped = query_extra.replace("\\", "\\\\").replace("'", "\\'")
            q_parts.append(f"name contains '{escaped}'")
        query = " and ".join(q_parts)
        try:
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name)",
                    pageSize=page_size,
                    orderBy="name",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
        except HttpError as exc:
            raise DriveServiceError(f"Failed to list folders: {exc}") from exc
        return response.get("files", [])

    def find_child_by_name(        self,
        parent_id: str,
        name: str,
        mime_type: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a non-trashed child with the exact name under parent_id."""
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        q_parts = [
            f"name = '{escaped}'",
            f"'{parent_id}' in parents",
            "trashed = false",
        ]
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        query = " and ".join(q_parts)
        try:
            response = (
                self._service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, mimeType, size)",
                    pageSize=10,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
        except HttpError as exc:
            raise DriveServiceError(f"Failed to search for '{name}': {exc}") from exc
        files = response.get("files", [])
        return files[0] if files else None

    def create_folder(self, name: str, parent_id: str) -> str:
        """Create a folder under parent_id and return its id."""
        metadata = {
            "name": name,
            "mimeType": FOLDER_MIME,
            "parents": [parent_id],
        }
        try:
            created = (
                self._service.files()
                .create(
                    body=metadata,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as exc:
            raise DriveServiceError(f"Failed to create folder '{name}': {exc}") from exc
        folder_id = created["id"]
        self._folder_cache[(parent_id, name)] = folder_id
        return folder_id

    def ensure_folder(self, name: str, parent_id: str) -> str:
        """Return existing folder id by name under parent, or create it."""
        cache_key = (parent_id, name)
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        existing = self.find_child_by_name(parent_id, name, mime_type=FOLDER_MIME)
        if existing:
            folder_id = existing["id"]
            self._folder_cache[cache_key] = folder_id
            return folder_id
        return self.create_folder(name, parent_id)

    def ensure_folder_path(self, parent_id: str, relative_parts: tuple[str, ...]) -> str:
        """Ensure nested folders exist for relative_parts under parent_id."""
        current_id = parent_id
        for part in relative_parts:
            if not part or part in (".", ".."):
                continue
            current_id = self.ensure_folder(part, current_id)
        return current_id

    def find_file_by_name(self, parent_id: str, name: str) -> dict[str, Any] | None:
        """Find a non-folder file with the given name under parent_id."""
        existing = self.find_child_by_name(parent_id, name)
        if not existing:
            return None
        if existing.get("mimeType") == FOLDER_MIME:
            return None
        return existing

    def same_name_and_size(self, remote: dict[str, Any], size_bytes: int) -> bool:
        """True when remote file size matches local size (conflict skip)."""
        remote_size = remote.get("size")
        if remote_size is None:
            return False
        try:
            return int(remote_size) == int(size_bytes)
        except (TypeError, ValueError):
            return False

    def upload_file(
        self,
        local_path: Path,
        parent_id: str,
        *,
        skip_if_same_name_size: bool = True,
    ) -> tuple[str, bool]:
        """
        Upload a local file into parent_id.

        Conflict resolution:
        - Same name + same size → skip (returns skipped=True)
        - Same name + different size → update existing Drive file content
        - No match → create new file

        Returns (file_id, skipped).
        """
        name = local_path.name
        try:
            size_bytes = local_path.stat().st_size
        except OSError as exc:
            raise DriveServiceError(f"Cannot stat {local_path}: {exc}") from exc

        existing = self.find_file_by_name(parent_id, name)
        if existing and skip_if_same_name_size and self.same_name_and_size(existing, size_bytes):
            logger.info("Skipping %s (same name+size on Drive)", local_path)
            return existing["id"], True

        mime_type, _ = mimetypes.guess_type(str(local_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        resumable = size_bytes >= RESUMABLE_THRESHOLD_BYTES
        media = MediaFileUpload(
            str(local_path),
            mimetype=mime_type,
            resumable=resumable,
            chunksize=256 * 1024,
        )

        try:
            if existing:
                updated = (
                    self._service.files()
                    .update(
                        fileId=existing["id"],
                        media_body=media,
                        fields="id",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                return updated["id"], False

            metadata = {"name": name, "parents": [parent_id]}
            created = (
                self._service.files()
                .create(
                    body=metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except HttpError as exc:
            raise DriveServiceError(f"Failed to upload {local_path}: {exc}") from exc
        except OSError as exc:
            raise DriveServiceError(f"Failed to read {local_path}: {exc}") from exc

        return created["id"], False
