"""Continuous local folder watching for auto-sync uploads."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.upload.folder_walker import FolderWalker

logger = logging.getLogger(__name__)

DEBOUNCE_MS = 1500


class _WatchHandler(FileSystemEventHandler):
    def __init__(self, watcher: "FolderWatcher", root: Path) -> None:
        super().__init__()
        self._watcher = watcher
        self._root = root

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher.schedule_file(self._root, Path(str(event.src_path)))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher.schedule_file(self._root, Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        dest = getattr(event, "dest_path", None)
        if dest:
            self._watcher.schedule_file(self._root, Path(str(dest)))


class FolderWatcher(QObject):
    """
    Watch one or more root folders recursively.

    Emits file_changed(root_path_str, file_path_str) after debounce so the
    UI can queue a single-file sync upload once writes settle.
    """

    file_changed = pyqtSignal(str, str)
    watch_error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._observer: Observer | None = None
        self._roots: dict[str, Path] = {}
        self._timers: dict[str, QTimer] = {}
        self._pending: dict[str, tuple[Path, Path]] = {}
        self._walker = FolderWalker()

    @property
    def is_watching(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def start(self, roots: list[Path]) -> None:
        self.stop()
        if not roots:
            return
        observer = Observer()
        for root in roots:
            try:
                resolved = root.expanduser().resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                self.watch_error.emit(f"Cannot watch {root}: {exc}")
                continue
            if not resolved.is_dir():
                self.watch_error.emit(f"Not a directory: {resolved}")
                continue
            handler = _WatchHandler(self, resolved)
            try:
                observer.schedule(handler, str(resolved), recursive=True)
            except OSError as exc:
                self.watch_error.emit(f"Failed to watch {resolved}: {exc}")
                continue
            self._roots[str(resolved)] = resolved
            logger.info("Watching %s", resolved)

        if not self._roots:
            return
        self._observer = observer
        observer.start()

    def stop(self) -> None:
        for timer in self._timers.values():
            timer.stop()
            timer.deleteLater()
        self._timers.clear()
        self._pending.clear()

        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except RuntimeError as exc:
                logger.warning("Observer stop issue: %s", exc)
            self._observer = None
        self._roots.clear()

    def schedule_file(self, root: Path, file_path: Path) -> None:
        try:
            resolved_file = file_path.resolve()
        except (OSError, RuntimeError):
            resolved_file = file_path

        if self._walker.should_skip_name(resolved_file.name):
            return
        try:
            resolved_file.relative_to(root)
        except ValueError:
            return

        key = str(resolved_file)
        self._pending[key] = (root, resolved_file)

        timer = self._timers.get(key)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda k=key: self._emit_pending(k))
            self._timers[key] = timer
        timer.start(DEBOUNCE_MS)

    def _emit_pending(self, key: str) -> None:
        pending = self._pending.pop(key, None)
        timer = self._timers.pop(key, None)
        if timer is not None:
            timer.deleteLater()
        if not pending:
            return
        root, file_path = pending
        if not file_path.is_file():
            return
        self.file_changed.emit(str(root), str(file_path))
