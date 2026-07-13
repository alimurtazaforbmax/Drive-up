"""Background QThread that uploads queued folders to Google Drive."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QMutex, QThread, pyqtSignal

from src.drive.drive_service import DriveService, DriveServiceError
from src.upload.folder_walker import FolderWalker
from src.upload.queue_model import QueueItemStatus, UploadQueueItem

logger = logging.getLogger(__name__)


class UploadWorker(QThread):
    """Upload one or more folder queue items without blocking the UI."""

    log_message = pyqtSignal(str)
    folder_started = pyqtSignal(int)
    folder_progress = pyqtSignal(int, int, int, str)  # row, percent, uploaded_files, path
    folder_finished = pyqtSignal(int, str, int, int)  # row, status, uploaded, skipped
    folder_failed = pyqtSignal(int, str)
    all_finished = pyqtSignal()

    def __init__(
        self,
        drive: DriveService,
        items: list[tuple[int, UploadQueueItem]],
        destination_parent_id: str,
        parent=None,
        *,
        single_file: Path | None = None,
        single_file_root: Path | None = None,
        single_file_row: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._drive = drive
        self._items = items
        self._destination_parent_id = destination_parent_id
        self._walker = FolderWalker()
        self._cancel_requested = False
        self._mutex = QMutex()
        self._single_file = single_file
        self._single_file_root = single_file_root
        self._single_file_row = single_file_row

    def request_cancel(self) -> None:
        self._mutex.lock()
        self._cancel_requested = True
        self._mutex.unlock()

    def _is_cancelled(self) -> bool:
        self._mutex.lock()
        value = self._cancel_requested
        self._mutex.unlock()
        return value

    def run(self) -> None:
        try:
            if self._single_file and self._single_file_root is not None:
                self._upload_single_file()
            else:
                self._upload_queue()
        finally:
            self.all_finished.emit()

    def _upload_queue(self) -> None:
        for row, item in self._items:
            if self._is_cancelled():
                self.folder_finished.emit(
                    row,
                    QueueItemStatus.CANCELLED.value,
                    item.uploaded_files,
                    item.skipped_files,
                )
                continue
            self.folder_started.emit(row)
            try:
                if item.is_file:
                    uploaded, skipped = self._upload_file_item(row, item.local_path)
                else:
                    uploaded, skipped = self._upload_folder(row, item.local_path)
                status = (
                    QueueItemStatus.CANCELLED.value
                    if self._is_cancelled()
                    else QueueItemStatus.DONE.value
                )
                self.folder_finished.emit(row, status, uploaded, skipped)
            except Exception as exc:
                logger.exception("Upload failed: %s", item.local_path)
                self.folder_failed.emit(row, str(exc))

    def _upload_single_file(self) -> None:
        assert self._single_file is not None
        assert self._single_file_root is not None
        row = self._single_file_row if self._single_file_row is not None else -1
        if row >= 0:
            self.folder_started.emit(row)
        try:
            root = self._single_file_root
            file_path = self._single_file
            if self._walker.should_skip_name(file_path.name):
                self.log_message.emit(f"Skipped watched file (filter): {file_path}")
                if row >= 0:
                    self.folder_finished.emit(row, QueueItemStatus.WATCHING.value, 0, 1)
                return

            root_folder_id = self._drive.ensure_folder(root.name, self._destination_parent_id)
            parts = self._walker.relative_parts(root, file_path)
            parent_id = self._drive.ensure_folder_path(root_folder_id, parts)
            file_id, skipped = self._drive.upload_file(file_path, parent_id)
            if skipped:
                self.log_message.emit(f"Skipped (same name+size): {file_path}")
            else:
                self.log_message.emit(f"Synced: {file_path} -> {file_id}")
            if row >= 0:
                self.folder_progress.emit(row, 100, 1, str(file_path))
                self.folder_finished.emit(
                    row,
                    QueueItemStatus.WATCHING.value,
                    0 if skipped else 1,
                    1 if skipped else 0,
                )
        except Exception as exc:
            logger.exception("Single-file sync failed: %s", self._single_file)
            self.log_message.emit(f"Sync error: {exc}")
            if row >= 0:
                self.folder_failed.emit(row, str(exc))

    def _upload_file_item(self, row: int, file_path: Path) -> tuple[int, int]:
        """Upload a single queued file into the Drive destination folder."""
        try:
            resolved = file_path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DriveServiceError(f"Cannot resolve file {file_path}: {exc}") from exc
        if not resolved.is_file():
            raise DriveServiceError(f"Not a file: {resolved}")
        if self._walker.should_skip_name(resolved.name):
            self.log_message.emit(f"Skipped (filter): {resolved}")
            self.folder_progress.emit(row, 100, 1, str(resolved))
            return 0, 1

        self.log_message.emit(f"Uploading file {resolved}")
        self.folder_progress.emit(row, 10, 0, str(resolved))
        _file_id, was_skipped = self._drive.upload_file(
            resolved,
            self._destination_parent_id,
        )
        if was_skipped:
            self.log_message.emit(f"Skipped (same name+size): {resolved}")
            self.folder_progress.emit(row, 100, 1, str(resolved))
            return 0, 1
        self.log_message.emit(f"Uploaded: {resolved}")
        self.folder_progress.emit(row, 100, 1, str(resolved))
        return 1, 0

    def _upload_folder(self, row: int, root: Path) -> tuple[int, int]:
        walk = self._walker.walk(root)
        self.log_message.emit(
            f"Scanning {walk.root}: {len(walk.files)} files "
            f"({walk.total_bytes} bytes)"
        )
        root_folder_id = self._drive.ensure_folder(
            walk.root.name,
            self._destination_parent_id,
        )
        uploaded = 0
        skipped = 0
        total = max(len(walk.files), 1)

        for index, file_path in enumerate(walk.files, start=1):
            if self._is_cancelled():
                self.log_message.emit("Upload cancelled.")
                break
            try:
                parts = self._walker.relative_parts(walk.root, file_path)
                parent_id = self._drive.ensure_folder_path(root_folder_id, parts)
                _file_id, was_skipped = self._drive.upload_file(file_path, parent_id)
                if was_skipped:
                    skipped += 1
                    self.log_message.emit(f"Skipped (same name+size): {file_path}")
                else:
                    uploaded += 1
                    self.log_message.emit(f"Uploaded: {file_path}")
            except (DriveServiceError, OSError) as exc:
                self.log_message.emit(f"Error uploading {file_path}: {exc}")
                raise

            percent = int(index * 100 / total)
            self.folder_progress.emit(row, percent, uploaded + skipped, str(file_path))

        return uploaded, skipped
