"""Qt list model for the multi-item upload queue (folders and files)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt


class QueueItemStatus(str, Enum):
    QUEUED = "Queued"
    UPLOADING = "Uploading"
    WATCHING = "Watching"
    DONE = "Done"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class QueueItemKind(str, Enum):
    FOLDER = "folder"
    FILE = "file"


@dataclass
class UploadQueueItem:
    local_path: Path
    kind: QueueItemKind = QueueItemKind.FOLDER
    file_count: int = 0
    total_bytes: int = 0
    status: QueueItemStatus = QueueItemStatus.QUEUED
    progress_percent: int = 0
    error_message: str = ""
    uploaded_files: int = 0
    skipped_files: int = 0

    @property
    def display_name(self) -> str:
        return self.local_path.name or str(self.local_path)

    @property
    def folder_name(self) -> str:
        """Back-compat alias for display_name."""
        return self.display_name

    @property
    def is_folder(self) -> bool:
        return self.kind == QueueItemKind.FOLDER

    @property
    def is_file(self) -> bool:
        return self.kind == QueueItemKind.FILE


class UploadQueueModel(QAbstractListModel):
    """List model of folders and files ready to upload."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[UploadQueueItem] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent and parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item.display_name
        if role == Qt.ItemDataRole.UserRole:
            return item
        if role == Qt.ItemDataRole.ToolTipRole:
            kind = "Folder" if item.is_folder else "File"
            if item.error_message:
                return f"{kind}: {item.local_path}\n{item.error_message}"
            return f"{kind}: {item.local_path}"
        return None

    def items(self) -> list[UploadQueueItem]:
        return list(self._items)

    def item_at(self, row: int) -> UploadQueueItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def add_item(self, item: UploadQueueItem) -> int:
        for existing in self._items:
            if existing.local_path == item.local_path:
                return -1
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()
        return row

    def remove_rows(self, rows: list[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self._items):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def update_item(self, row: int, **kwargs) -> None:
        if not (0 <= row < len(self._items)):
            return
        item = self._items[row]
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        model_index = self.index(row, 0)
        self.dataChanged.emit(model_index, model_index)

    def paths(self) -> list[Path]:
        return [item.local_path for item in self._items]

    def folder_paths(self) -> list[Path]:
        return [item.local_path for item in self._items if item.is_folder]


def format_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num} B"
