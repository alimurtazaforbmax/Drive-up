"""Main application window."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
)

from src.auth.google_auth import GoogleAuth, GoogleAuthError, MissingClientSecretError
from src.drive.drive_service import DriveService, DriveServiceError
from src.ui.background import GradientBackground
from src.ui.folder_delegate import FolderItemDelegate
from src.ui.google_setup_dialog import GoogleSetupDialog
from src.upload.folder_walker import FolderWalker
from src.upload.folder_watcher import FolderWatcher
from src.upload.queue_model import (
    QueueItemKind,
    QueueItemStatus,
    UploadQueueItem,
    UploadQueueModel,
)
from src.upload.upload_worker import UploadWorker
logger = logging.getLogger(__name__)


class DestinationPickerDialog(QDialog):
    """Pick a Drive folder as the upload destination parent."""

    def __init__(self, drive: DriveService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Drive Destination")
        self.resize(480, 420)
        self._drive = drive
        self._selected_id = "root"
        self._selected_name = "My Drive"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        heading = QLabel("Where should folders land?")
        heading.setObjectName("titleLabel")
        hint = QLabel("Pick My Drive root or a folder you already have on Drive.")
        hint.setObjectName("subtitleLabel")
        hint.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter folders by name…")
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("secondaryButton")
        search_row.addWidget(self._search)
        search_row.addWidget(self._refresh_btn)
        layout.addLayout(search_row)

        self._list = QListWidget()
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_btn.clicked.connect(self._load)
        self._search.returnPressed.connect(self._load)
        self._list.itemSelectionChanged.connect(self._on_select)
        self._load()

    def _load(self) -> None:
        self._list.clear()
        root_item = QListWidgetItem("My Drive (root)")
        root_item.setData(Qt.ItemDataRole.UserRole, ("root", "My Drive"))
        self._list.addItem(root_item)
        try:
            folders = self._drive.list_folders(
                parent_id="root",
                query_extra=self._search.text().strip(),
            )
        except DriveServiceError as exc:
            QMessageBox.warning(self, "Drive Error", str(exc))
            return
        for folder in folders:
            item = QListWidgetItem(folder["name"])
            item.setData(Qt.ItemDataRole.UserRole, (folder["id"], folder["name"]))
            self._list.addItem(item)

    def _on_select(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        folder_id, name = item.data(Qt.ItemDataRole.UserRole)
        self._selected_id = folder_id
        self._selected_name = name

    def selected(self) -> tuple[str, str]:
        return self._selected_id, self._selected_name


class MainWindow(QMainWindow):
    def __init__(self, auth: GoogleAuth | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DriveUp - Google Drive Folder Uploader")
        self.resize(1040, 760)
        self.setMinimumSize(860, 640)

        self._auth = auth or GoogleAuth()
        self._drive: DriveService | None = None
        self._destination_id = "root"
        self._destination_name = "My Drive"
        self._worker: UploadWorker | None = None
        self._sync_worker: UploadWorker | None = None
        self._walker = FolderWalker()
        self._queue_model = UploadQueueModel(self)
        self._watcher = FolderWatcher(self)
        self._pending_sync: list[tuple[Path, Path, int]] = []
        self._suppress_account_change = False
        self._upload_batch_total = 0
        self._upload_batch_done = 0

        self._build_ui()
        self._connect_signals()
        self._refresh_auth_ui()
        self._update_upload_empty_state()

    def _build_ui(self) -> None:
        central = GradientBackground()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        root.addWidget(self._build_header())
        root.addWidget(self._build_upload_panel(), stretch=4)
        root.addWidget(self._build_progress_panel())
        root.addWidget(self._build_log_panel(), stretch=1)

        self._cancel_btn.setEnabled(False)
        self._stop_watch_btn.setEnabled(False)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("appHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(10)

        brand = QLabel("Drive")
        brand.setObjectName("brandLabel")
        accent = QLabel("Up")
        accent.setObjectName("brandAccent")
        layout.addWidget(brand)
        layout.addWidget(accent)
        layout.addSpacing(8)

        account_wrap = QVBoxLayout()
        account_wrap.setSpacing(2)
        account_caption = QLabel("DRIVE")
        account_caption.setObjectName("compactMeta")
        self._account_combo = QComboBox()
        self._account_combo.setMinimumWidth(200)
        self._account_combo.setToolTip("Switch between connected Google Drive accounts")
        account_wrap.addWidget(account_caption)
        account_wrap.addWidget(self._account_combo)
        layout.addLayout(account_wrap)

        dest_wrap = QVBoxLayout()
        dest_wrap.setSpacing(2)
        dest_caption = QLabel("FOLDER")
        dest_caption.setObjectName("compactMeta")
        self._choose_dest_btn = QPushButton(self._destination_name)
        self._choose_dest_btn.setObjectName("headerSecondary")
        self._choose_dest_btn.setMinimumWidth(140)
        self._choose_dest_btn.setToolTip("Choose destination folder on this Drive")
        dest_wrap.addWidget(dest_caption)
        dest_wrap.addWidget(self._choose_dest_btn)
        layout.addLayout(dest_wrap)

        layout.addStretch(1)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connectButton")
        self._connect_btn.setToolTip("Connect a Google Drive account")
        self._add_account_btn = QPushButton("Add Drive")
        self._add_account_btn.setObjectName("addDriveButton")
        self._add_account_btn.setToolTip("Connect another Google account")
        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnectButton")
        self._disconnect_btn.setToolTip("Remove the selected Drive account")
        layout.addWidget(self._connect_btn)
        layout.addWidget(self._add_account_btn)
        layout.addWidget(self._disconnect_btn)
        return header

    def _build_upload_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("uploadPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("Items to upload")
        title.setObjectName("sectionTitle")
        self._queue_count = QLabel("0 items")
        self._queue_count.setObjectName("queueCount")
        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self._queue_count)
        layout.addLayout(header_row)

        legend = QLabel(
            '<span style="color:#5a6b7a">Waiting</span>  ·  '
            '<span style="color:#1a73e8">Uploading</span>  ·  '
            '<span style="color:#0f9d58">Uploaded</span>  ·  '
            '<span style="color:#d93025">Failed</span>'
            '  ·  Right-click a folder to remove or retry it'
        )
        legend.setObjectName("metaLabel")
        legend.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(legend)

        self._upload_stack = QStackedWidget()

        drop = QFrame()
        drop.setObjectName("dropZone")
        drop.setCursor(Qt.CursorShape.PointingHandCursor)
        drop_layout = QVBoxLayout(drop)
        drop_layout.setContentsMargins(24, 36, 24, 36)
        drop_layout.setSpacing(10)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_title = QLabel("Select folders or files to upload")
        drop_title.setObjectName("dropTitle")
        drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_sub = QLabel(
            "Add whole folders or individual files.\n"
            "They appear in the grid with clear upload status."
        )
        drop_sub.setObjectName("dropSubtitle")
        drop_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_sub.setWordWrap(True)
        browse_row = QHBoxLayout()
        browse_row.setSpacing(10)
        self._browse_btn = QPushButton("Browse folders")
        self._browse_btn.setObjectName("browseButton")
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_files_btn = QPushButton("Browse files")
        self._browse_files_btn.setObjectName("addDriveButton")
        self._browse_files_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_row.addStretch(1)
        browse_row.addWidget(self._browse_btn)
        browse_row.addWidget(self._browse_files_btn)
        browse_row.addStretch(1)
        drop_layout.addWidget(drop_title)
        drop_layout.addWidget(drop_sub)
        drop_layout.addSpacing(8)
        drop_layout.addLayout(browse_row)
        self._drop_zone = drop
        self._drop_zone.mousePressEvent = (  # type: ignore[method-assign]
            lambda event: self._on_add_folder()
        )
        self._upload_stack.addWidget(drop)

        table_wrap = QFrame()
        table_wrap.setObjectName("panelFrame")
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(6, 6, 6, 6)
        table_layout.setSpacing(0)
        self._folder_list = QListView()
        self._folder_list.setModel(self._queue_model)
        self._folder_list.setItemDelegate(FolderItemDelegate(self._folder_list))
        self._folder_list.setViewMode(QListView.ViewMode.IconMode)
        self._folder_list.setFlow(QListView.Flow.LeftToRight)
        self._folder_list.setWrapping(True)
        self._folder_list.setResizeMode(QListView.ResizeMode.Adjust)
        self._folder_list.setMovement(QListView.Movement.Static)
        self._folder_list.setGridSize(QSize(168, 180))
        self._folder_list.setSpacing(8)
        self._folder_list.setUniformItemSizes(True)
        self._folder_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._folder_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._folder_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._folder_list.setObjectName("folderList")
        self._folder_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._folder_list.customContextMenuRequested.connect(self._on_folder_context_menu)
        table_layout.addWidget(self._folder_list)
        self._upload_stack.addWidget(table_wrap)
        layout.addWidget(self._upload_stack, stretch=1)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self._add_btn = QPushButton("Add folders")
        self._add_btn.setObjectName("addFoldersButton")
        self._add_btn.setToolTip("Open the system folder picker")
        self._add_files_btn = QPushButton("Add files")
        self._add_files_btn.setObjectName("addDriveButton")
        self._add_files_btn.setToolTip("Pick one or more files to upload")
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName("removeButton")
        self._remove_btn.setToolTip("Remove selected item(s)")
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("ghostButton")
        self._retry_btn = QPushButton("Retry failed")
        self._retry_btn.setObjectName("retryButton")
        self._retry_btn.setToolTip("Re-queue all failed items")
        for btn in (
            self._add_btn,
            self._add_files_btn,
            self._remove_btn,
            self._clear_btn,
            self._retry_btn,
        ):
            tools.addWidget(btn)
        tools.addStretch(1)
        layout.addLayout(tools)

        sync_row = QHBoxLayout()
        sync_row.setSpacing(8)
        self._watch_checkbox = QCheckBox("Keep syncing new and changed files")
        self._start_watch_btn = QPushButton("Start watching")
        self._start_watch_btn.setObjectName("secondaryButton")
        self._stop_watch_btn = QPushButton("Stop watching")
        self._stop_watch_btn.setObjectName("secondaryButton")
        sync_row.addWidget(self._watch_checkbox, stretch=1)
        sync_row.addWidget(self._start_watch_btn)
        sync_row.addWidget(self._stop_watch_btn)
        layout.addLayout(sync_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dangerButton")
        self._start_btn = QPushButton("Start upload")
        self._start_btn.setObjectName("primaryCta")
        action_row.addStretch(1)
        action_row.addWidget(self._cancel_btn)
        action_row.addWidget(self._start_btn)
        layout.addLayout(action_row)
        return panel

    def _build_progress_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panelFrame")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        row = QHBoxLayout()
        label = QLabel("Overall progress")
        label.setObjectName("sectionTitle")
        self._progress_meta = QLabel("Idle")
        self._progress_meta.setObjectName("metaLabel")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self._progress_meta)
        layout.addLayout(row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        layout.addWidget(self._progress)
        return panel

    def _build_log_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panelFrame")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QLabel("Activity")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setMaximumHeight(150)
        self._log.setPlaceholderText("Upload and sync activity appears here…")
        layout.addWidget(self._log)
        return panel

    def _connect_signals(self) -> None:
        self._connect_btn.clicked.connect(self._on_connect)
        self._add_account_btn.clicked.connect(self._on_add_account)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        self._choose_dest_btn.clicked.connect(self._on_choose_destination)
        self._account_combo.currentIndexChanged.connect(self._on_account_changed)
        self._add_btn.clicked.connect(self._on_add_folder)
        self._add_files_btn.clicked.connect(self._on_add_files)
        self._browse_btn.clicked.connect(self._on_add_folder)
        self._browse_files_btn.clicked.connect(self._on_add_files)
        self._remove_btn.clicked.connect(self._on_remove)
        self._clear_btn.clicked.connect(self._on_clear)
        self._retry_btn.clicked.connect(self._on_retry_failed)
        self._start_btn.clicked.connect(self._on_start_upload)
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._start_watch_btn.clicked.connect(self._on_start_watching)
        self._stop_watch_btn.clicked.connect(self._on_stop_watching)
        self._watcher.file_changed.connect(self._on_watched_file)
        self._watcher.watch_error.connect(self._append_log)
        self._queue_model.rowsInserted.connect(lambda *_: self._update_upload_empty_state())
        self._queue_model.rowsRemoved.connect(lambda *_: self._update_upload_empty_state())
        self._queue_model.modelReset.connect(self._update_upload_empty_state)

    def _append_log(self, message: str) -> None:
        self._log.appendPlainText(message)

    def _update_upload_empty_state(self) -> None:
        count = self._queue_model.rowCount()
        folders = sum(1 for item in self._queue_model.items() if item.is_folder)
        files = count - folders
        if folders and files:
            self._queue_count.setText(f"{folders} folders · {files} files")
        elif files:
            self._queue_count.setText(f"{files} file" + ("s" if files != 1 else ""))
        else:
            self._queue_count.setText(f"{folders} folder" + ("s" if folders != 1 else ""))
        self._upload_stack.setCurrentIndex(0 if count == 0 else 1)
        has_items = count > 0
        busy = bool(self._worker and self._worker.isRunning())
        self._remove_btn.setEnabled(has_items and not busy)
        self._clear_btn.setEnabled(has_items and not busy)
        self._start_btn.setEnabled(has_items and not busy)

    def _load_active_destination(self) -> None:
        account = self._auth.active_account()
        if account is None:
            self._destination_id = "root"
            self._destination_name = "My Drive"
        else:
            self._destination_id = account.destination_id or "root"
            self._destination_name = account.destination_name or "My Drive"
        self._choose_dest_btn.setText(self._destination_name)

    def _rebuild_account_combo(self) -> None:
        self._suppress_account_change = True
        self._account_combo.clear()
        accounts = self._auth.list_accounts()
        active = self._auth.active_account()
        if not accounts:
            self._account_combo.addItem("No Drive connected", "")
            self._account_combo.setEnabled(False)
        else:
            self._account_combo.setEnabled(True)
            active_index = 0
            for index, account in enumerate(accounts):
                self._account_combo.addItem(account.label(), account.id)
                if active and account.id == active.id:
                    active_index = index
            self._account_combo.setCurrentIndex(active_index)
        self._suppress_account_change = False

    def _refresh_auth_ui(self) -> None:
        connected = self._auth.is_authenticated
        if connected:
            try:
                self._drive = DriveService(self._auth.build_drive_service())
            except GoogleAuthError as exc:
                self._append_log(str(exc))
                self._drive = None
                connected = False
        else:
            self._drive = None

        self._rebuild_account_combo()
        self._load_active_destination()

        self._connect_btn.setVisible(not connected)
        self._connect_btn.setEnabled(not connected)
        self._add_account_btn.setVisible(connected)
        self._add_account_btn.setEnabled(connected)
        self._disconnect_btn.setEnabled(connected)
        self._choose_dest_btn.setEnabled(connected)
        self._account_combo.setEnabled(connected and self._account_combo.count() > 0)

    def _ensure_drive(self) -> DriveService | None:
        if self._drive is not None and self._auth.is_authenticated:
            return self._drive
        if not self._auth.is_authenticated:
            if not self._run_sign_in_flow(add_account=True):
                return None
        try:
            self._drive = DriveService(self._auth.build_drive_service())
            self._refresh_auth_ui()
            return self._drive
        except MissingClientSecretError:
            if self._run_sign_in_flow(add_account=True):
                return self._drive
            return None
        except GoogleAuthError as exc:
            QMessageBox.warning(self, "Authentication Required", str(exc))
            return None

    def _run_sign_in_flow(self, *, add_account: bool = False) -> bool:
        """Import OAuth client if needed, then open Google browser sign-in."""
        if not self._auth.has_client_secret():
            dialog = GoogleSetupDialog(self._auth, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._append_log("Sign-in cancelled.")
                return False

        self._append_log("Opening Google sign-in in your browser…")
        try:
            QMessageBox.information(
                self,
                "Google Sign-In",
                "Your browser will open to Google.\n\n"
                "Choose the Google account for this Drive, then click Allow.\n\n"
                "You do not need to copy any code — Google redirects back to "
                "this app on localhost (127.0.0.1).",
            )
            self._auth.authenticate(add_account=add_account or not self._auth.list_accounts())
            self._drive = DriveService(self._auth.build_drive_service())
            account = self._auth.active_account()
            label = account.label() if account else "Google Drive"
            self._append_log(f"Connected: {label}")
            QMessageBox.information(
                self,
                "Connected",
                f"Connected to {label}.\n"
                "Use Add Drive to connect another account, or the Drive menu to switch.",
            )
            return True
        except MissingClientSecretError:
            QMessageBox.warning(
                self,
                "Setup Incomplete",
                "App credentials are still missing. Import the Desktop OAuth "
                "JSON, then try Connect again.",
            )
            return False
        except GoogleAuthError as exc:
            QMessageBox.critical(self, "Sign-in Failed", str(exc))
            self._append_log(f"Sign-in failed: {exc}")
            return False
        finally:
            self._refresh_auth_ui()

    def _on_connect(self) -> None:
        self._run_sign_in_flow(add_account=True)

    def _on_add_account(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Finish or cancel the upload before adding another Drive.")
            return
        self._run_sign_in_flow(add_account=True)

    def _on_account_changed(self, index: int) -> None:
        if self._suppress_account_change or index < 0:
            return
        account_id = self._account_combo.itemData(index)
        if not account_id:
            return
        active = self._auth.active_account()
        if active and active.id == account_id:
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Finish or cancel the upload before switching Drive.")
            self._rebuild_account_combo()
            return
        self._on_stop_watching()
        try:
            account = self._auth.set_active_account(str(account_id))
            self._drive = DriveService(self._auth.build_drive_service())
            self._load_active_destination()
            self._append_log(f"Switched to Drive: {account.label()}")
        except GoogleAuthError as exc:
            QMessageBox.warning(self, "Switch Failed", str(exc))
        self._refresh_auth_ui()

    def _on_disconnect(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Cancel the upload before disconnecting.")
            return
        self._on_stop_watching()
        account = self._auth.active_account()
        label = account.label() if account else "Drive"
        self._auth.disconnect()
        self._drive = None
        self._append_log(f"Disconnected: {label}")
        self._refresh_auth_ui()

    def _on_choose_destination(self) -> None:
        drive = self._ensure_drive()
        if drive is None:
            return
        dialog = DestinationPickerDialog(drive, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._destination_id, self._destination_name = dialog.selected()
            self._auth.update_active_destination(
                self._destination_id,
                self._destination_name,
            )
            self._choose_dest_btn.setText(self._destination_name)
            self._append_log(
                f"Destination set to: {self._destination_name} ({self._destination_id})"
            )

    def _on_add_folder(self) -> None:
        """Open the native OS folder picker and queue the chosen directory."""
        path_str = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Upload",
            str(Path.home()),
        )
        if not path_str:
            return

        result = self._queue_folder(Path(path_str))
        if result == "duplicate":
            QMessageBox.information(
                self,
                "Already Queued",
                "That folder is already in the queue.",
            )
        elif result == "error":
            QMessageBox.warning(
                self,
                "Invalid Folder",
                "That folder could not be added. Check the activity log for details.",
            )
        else:
            self._append_log("Folder added to the queue.")

    def _on_add_files(self) -> None:
        """Open the native multi-file picker and queue each chosen file."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Upload",
            str(Path.home()),
            "All files (*.*)",
        )
        if not paths:
            return

        added = 0
        dupes = 0
        errors = 0
        for path_str in paths:
            result = self._queue_file(Path(path_str))
            if result == "added":
                added += 1
            elif result == "duplicate":
                dupes += 1
            else:
                errors += 1

        if added:
            self._append_log(f"Added {added} file(s) to the queue.")
        if dupes:
            self._append_log(f"Skipped {dupes} file(s) already in the queue.")
        if errors:
            self._append_log(f"Could not add {errors} file(s).")
        if not added and dupes and not errors:
            QMessageBox.information(
                self,
                "Already Queued",
                "Those files are already in the queue.",
            )

    def _queue_folder(self, path: Path) -> str:
        """Scan and enqueue one folder. Returns added | duplicate | error."""
        try:
            walk = self._walker.walk(path)
        except (OSError, FileNotFoundError, NotADirectoryError) as exc:
            self._append_log(f"Skipped {path}: {exc}")
            return "error"
        item = UploadQueueItem(
            local_path=walk.root,
            kind=QueueItemKind.FOLDER,
            file_count=len(walk.files),
            total_bytes=walk.total_bytes,
            status=QueueItemStatus.QUEUED,
        )
        row = self._queue_model.add_item(item)
        if row < 0:
            return "duplicate"
        self._append_log(
            f"Queued folder {walk.root} ({len(walk.files)} files, {walk.total_bytes} bytes)"
        )
        if walk.skipped:
            self._append_log(f"  ({len(walk.skipped)} paths skipped by filter)")
        return "added"

    def _queue_file(self, path: Path) -> str:
        """Enqueue one file. Returns added | duplicate | error."""
        try:
            resolved = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            self._append_log(f"Skipped {path}: {exc}")
            return "error"
        if not resolved.is_file():
            self._append_log(f"Skipped (not a file): {resolved}")
            return "error"
        if self._walker.should_skip_name(resolved.name):
            self._append_log(f"Skipped (filter): {resolved}")
            return "error"
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            self._append_log(f"Skipped {resolved}: {exc}")
            return "error"

        item = UploadQueueItem(
            local_path=resolved,
            kind=QueueItemKind.FILE,
            file_count=1,
            total_bytes=size,
            status=QueueItemStatus.QUEUED,
        )
        row = self._queue_model.add_item(item)
        if row < 0:
            return "duplicate"
        self._append_log(f"Queued file {resolved} ({size} bytes)")
        return "added"

    def _selected_rows(self) -> list[int]:
        indexes = self._folder_list.selectionModel().selectedIndexes()
        return sorted({index.row() for index in indexes})

    def _on_folder_context_menu(self, pos) -> None:
        index = self._folder_list.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        item = self._queue_model.item_at(row)
        if item is None:
            return

        # Keep the right-clicked card selected for clarity
        self._folder_list.setCurrentIndex(index)

        menu = QMenu(self)
        remove_action = QAction("Remove this item", self)
        retry_action = QAction("Retry this item", self)
        retry_action.setEnabled(item.status == QueueItemStatus.FAILED)
        busy = bool(self._worker and self._worker.isRunning())
        remove_action.setEnabled(not busy)
        menu.addAction(remove_action)
        menu.addAction(retry_action)

        chosen = menu.exec(self._folder_list.viewport().mapToGlobal(pos))
        if chosen == remove_action:
            self._remove_rows([row])
        elif chosen == retry_action:
            self._retry_rows([row])

    def _on_remove(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Select an item first, or right-click → Remove this item.",
            )
            return
        self._remove_rows(rows)

    def _remove_rows(self, rows: list[int]) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Cancel the upload before removing folders.")
            return
        self._queue_model.remove_rows(rows)
        self._update_upload_empty_state()

    def _on_clear(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(
                self, "Busy", "Cancel the upload before clearing the queue."
            )
            return
        self._on_stop_watching()
        self._queue_model.clear()
        self._progress.setValue(0)
        self._progress_meta.setText("Idle")
        self._update_upload_empty_state()

    def _on_retry_failed(self) -> None:
        rows = [
            row
            for row, item in enumerate(self._queue_model.items())
            if item.status == QueueItemStatus.FAILED
        ]
        if not rows:
            QMessageBox.information(self, "Nothing to Retry", "No failed folders in the queue.")
            return
        self._retry_rows(rows)

    def _retry_rows(self, rows: list[int]) -> None:
        for row in rows:
            item = self._queue_model.item_at(row)
            if item is None or item.status != QueueItemStatus.FAILED:
                continue
            self._queue_model.update_item(
                row,
                status=QueueItemStatus.QUEUED,
                progress_percent=0,
                error_message="",
                uploaded_files=0,
                skipped_files=0,
            )
        self._append_log(f"Re-queued {len(rows)} folder(s).")

    def _on_start_upload(self) -> None:
        drive = self._ensure_drive()
        if drive is None:
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "An upload is already running.")
            return

        items: list[tuple[int, UploadQueueItem]] = []
        for row, item in enumerate(self._queue_model.items()):
            if item.status in {
                QueueItemStatus.QUEUED,
                QueueItemStatus.FAILED,
                QueueItemStatus.CANCELLED,
            }:
                items.append((row, item))
        if not items:
            QMessageBox.information(
                self,
                "Nothing to Upload",
                "Add folders or files, or retry failed items.",
            )
            return

        self._worker = UploadWorker(drive, items, self._destination_id, self)
        self._worker.log_message.connect(self._append_log)
        self._worker.folder_started.connect(self._on_folder_started)
        self._worker.folder_progress.connect(self._on_folder_progress)
        self._worker.folder_finished.connect(self._on_folder_finished)
        self._worker.folder_failed.connect(self._on_folder_failed)
        self._worker.all_finished.connect(self._on_all_finished)
        self._upload_batch_total = len(items)
        self._upload_batch_done = 0
        self._set_upload_controls(busy=True)
        self._progress.setValue(0)
        self._progress.setFormat(f"0/{self._upload_batch_total} folders · %p%")
        self._progress_meta.setText(
            f"Uploading 0/{self._upload_batch_total} folders…"
        )
        self._append_log("Starting upload…")
        self._worker.start()

    def _set_upload_controls(self, *, busy: bool) -> None:
        self._cancel_btn.setEnabled(busy)
        self._add_btn.setEnabled(not busy)
        self._add_files_btn.setEnabled(not busy)
        self._browse_btn.setEnabled(not busy)
        self._browse_files_btn.setEnabled(not busy)
        self._clear_btn.setEnabled(not busy and self._queue_model.rowCount() > 0)
        if not busy:
            self._update_upload_empty_state()
        else:
            self._start_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._progress_meta.setText("Cancelling…")
            self._append_log("Cancel requested…")

    def _set_overall_progress(self, current_folder_percent: int, detail: str) -> None:
        total = max(self._upload_batch_total, 1)
        overall = int(
            ((self._upload_batch_done + (current_folder_percent / 100.0)) / total) * 100
        )
        overall = max(0, min(100, overall))
        self._progress.setValue(overall)
        self._progress.setFormat(
            f"{self._upload_batch_done}/{self._upload_batch_total} folders · %p%"
        )
        self._progress_meta.setText(detail)

    def _on_folder_started(self, row: int) -> None:
        self._queue_model.update_item(
            row,
            status=QueueItemStatus.UPLOADING,
            progress_percent=0,
            error_message="",
        )
        self._set_overall_progress(
            0,
            f"Uploading folder {self._upload_batch_done + 1}/{self._upload_batch_total}…",
        )

    def _on_folder_progress(
        self, row: int, percent: int, done_files: int, path: str
    ) -> None:
        self._queue_model.update_item(row, progress_percent=percent)
        name = Path(path).name
        self._set_overall_progress(
            percent,
            f"{name} · {done_files} file(s) · "
            f"folder {self._upload_batch_done + 1}/{self._upload_batch_total}",
        )

    def _on_folder_finished(
        self, row: int, status: str, uploaded: int, skipped: int
    ) -> None:
        try:
            status_enum = QueueItemStatus(status)
        except ValueError:
            status_enum = QueueItemStatus.DONE
        if self._watcher.is_watching and status_enum == QueueItemStatus.DONE:
            status_enum = QueueItemStatus.WATCHING
        self._queue_model.update_item(
            row,
            status=status_enum,
            progress_percent=100 if status_enum != QueueItemStatus.CANCELLED else 0,
            uploaded_files=uploaded,
            skipped_files=skipped,
        )
        if self._upload_batch_total:
            self._upload_batch_done = min(
                self._upload_batch_done + 1,
                self._upload_batch_total,
            )
            self._set_overall_progress(
                0 if self._upload_batch_done < self._upload_batch_total else 100,
                f"Finished {self._upload_batch_done}/{self._upload_batch_total} folders",
            )
        self._append_log(
            f"Folder row {row}: {status_enum.value} "
            f"(uploaded={uploaded}, skipped={skipped})"
        )

    def _on_folder_failed(self, row: int, message: str) -> None:
        self._queue_model.update_item(
            row,
            status=QueueItemStatus.FAILED,
            error_message=message,
        )
        if self._upload_batch_total:
            self._upload_batch_done = min(
                self._upload_batch_done + 1,
                self._upload_batch_total,
            )
            self._set_overall_progress(
                0,
                f"Error on folder {self._upload_batch_done}/{self._upload_batch_total}",
            )
        else:
            self._progress_meta.setText("Upload error")
        self._append_log(f"Folder row {row} failed: {message}")

    def _on_all_finished(self) -> None:
        self._set_upload_controls(busy=False)
        if self._upload_batch_total:
            self._progress.setValue(100)
            self._progress.setFormat(
                f"{self._upload_batch_total}/{self._upload_batch_total} folders · %p%"
            )
            self._progress_meta.setText("All folders finished")
        else:
            self._progress_meta.setText("Done")
        self._append_log("Queue finished.")
        if self._watch_checkbox.isChecked() and not self._watcher.is_watching:
            self._on_start_watching()
        self._drain_pending_sync()

    def _on_start_watching(self) -> None:
        drive = self._ensure_drive()
        if drive is None:
            return
        roots = self._queue_model.folder_paths()
        if not roots:
            QMessageBox.information(
                self,
                "No Folders",
                "Continuous sync watches folders only. Add at least one folder first.",
            )
            return
        self._watch_checkbox.setChecked(True)
        self._watcher.start(roots)
        for row, item in enumerate(self._queue_model.items()):
            if item.status in {QueueItemStatus.DONE, QueueItemStatus.QUEUED}:
                self._queue_model.update_item(row, status=QueueItemStatus.WATCHING)
        self._start_watch_btn.setEnabled(False)
        self._stop_watch_btn.setEnabled(True)
        self._progress_meta.setText("Watching for changes")
        self._append_log(f"Continuous sync enabled for {len(roots)} folder(s).")

    def _on_stop_watching(self) -> None:
        if self._watcher.is_watching:
            self._watcher.stop()
            self._append_log("Continuous sync stopped.")
        self._start_watch_btn.setEnabled(True)
        self._stop_watch_btn.setEnabled(False)
        self._progress_meta.setText("Idle")
        for row, item in enumerate(self._queue_model.items()):
            if item.status == QueueItemStatus.WATCHING:
                self._queue_model.update_item(row, status=QueueItemStatus.DONE)

    def _on_watched_file(self, root_str: str, file_str: str) -> None:
        root = Path(root_str)
        file_path = Path(file_str)
        row = self._row_for_root(root)
        self._append_log(f"Change detected: {file_path}")
        self._enqueue_sync(root, file_path, row)

    def _row_for_root(self, root: Path) -> int:
        for row, item in enumerate(self._queue_model.items()):
            if item.local_path == root:
                return row
        return -1

    def _enqueue_sync(self, root: Path, file_path: Path, row: int) -> None:
        if (self._worker and self._worker.isRunning()) or (
            self._sync_worker and self._sync_worker.isRunning()
        ):
            self._pending_sync.append((root, file_path, row))
            return
        self._start_sync_worker(root, file_path, row)

    def _start_sync_worker(self, root: Path, file_path: Path, row: int) -> None:
        drive = self._ensure_drive()
        if drive is None:
            return
        self._sync_worker = UploadWorker(
            drive,
            [],
            self._destination_id,
            self,
            single_file=file_path,
            single_file_root=root,
            single_file_row=row if row >= 0 else None,
        )
        self._sync_worker.log_message.connect(self._append_log)
        self._sync_worker.folder_progress.connect(self._on_folder_progress)
        self._sync_worker.folder_failed.connect(self._on_folder_failed)
        self._sync_worker.all_finished.connect(self._drain_pending_sync)
        self._progress_meta.setText(f"Syncing {file_path.name}")
        self._sync_worker.start()

    def _drain_pending_sync(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._sync_worker and self._sync_worker.isRunning():
            return
        if not self._pending_sync:
            if self._watcher.is_watching:
                self._progress_meta.setText("Watching for changes")
            return
        root, file_path, row = self._pending_sync.pop(0)
        self._start_sync_worker(root, file_path, row)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._on_stop_watching()
        if self._worker and self._worker.isRunning():
            self._worker.request_cancel()
            self._worker.wait(3000)
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.request_cancel()
            self._sync_worker.wait(3000)
        super().closeEvent(event)
