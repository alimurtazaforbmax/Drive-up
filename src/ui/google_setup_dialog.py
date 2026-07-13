"""One-time Google OAuth client setup + sign-in helper dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.auth.google_auth import GoogleAuth, GoogleAuthError

CONSOLE_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"
DRIVE_API_URL = "https://console.cloud.google.com/apis/library/drive.googleapis.com"


class GoogleSetupDialog(QDialog):
    """Guide the user through importing a Desktop OAuth client JSON once."""

    def __init__(self, auth: GoogleAuth, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Google Drive")
        self.resize(560, 480)
        self._auth = auth

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Sign in with Google")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        body = QLabel(
            "When you continue, DriveUp uses the modern desktop OAuth flow:\n"
            "opens your browser → you log in → Allow → Google redirects to "
            "http://127.0.0.1 on this PC → the app catches the code automatically "
            "and stores tokens.\n\n"
            "You never copy or paste an authorization code.\n\n"
            "One-time only: import the Desktop OAuth client JSON from Google Cloud "
            "so Google knows which app is asking. That is the app ID, not your login."
        )
        body.setWordWrap(True)
        body.setObjectName("subtitleLabel")
        layout.addWidget(body)

        steps_panel = QFrame()
        steps_panel.setObjectName("panelFrame")
        steps_layout = QVBoxLayout(steps_panel)
        steps_layout.setContentsMargins(14, 12, 14, 12)
        steps = QLabel(
            "<b>One-time app setup</b>"
            "<ol>"
            "<li>Enable the <b>Google Drive API</b>.</li>"
            "<li>Create <b>OAuth client ID</b> → type <b>Desktop app</b>.</li>"
            "<li>Download the JSON → click <b>Import JSON</b>.</li>"
            "</ol>"
            "<b>Sign-in (automatic — no code copying)</b>"
            "<ol>"
            "<li>App opens your browser and listens on <code>127.0.0.1</code>.</li>"
            "<li>You log into Google and click <b>Allow</b>.</li>"
            "<li>Google redirects back to the app; tokens are saved.</li>"
            "<li>Upload / sync anytime until you Disconnect.</li>"
            "</ol>"
        )
        steps.setWordWrap(True)
        steps_layout.addWidget(steps)
        layout.addWidget(steps_panel)
        self._status = QLabel(self._status_text())
        self._status.setObjectName("statusText")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._open_api_btn = QPushButton("Enable Drive API")
        self._open_api_btn.setObjectName("secondaryButton")
        self._open_console_btn = QPushButton("Open Credentials")
        self._open_console_btn.setObjectName("secondaryButton")
        self._import_btn = QPushButton("Import JSON…")
        self._import_btn.setObjectName("primaryCta")
        btn_row.addWidget(self._open_api_btn)
        btn_row.addWidget(self._open_console_btn)
        btn_row.addWidget(self._import_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox()
        self._continue_btn = buttons.addButton(
            "Continue to Google Sign-In",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_continue)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._open_api_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DRIVE_API_URL))
        )
        self._open_console_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CONSOLE_CREDENTIALS_URL))
        )
        self._import_btn.clicked.connect(self._on_import)
        self._refresh_continue()

    def _status_text(self) -> str:
        if self._auth.has_client_secret():
            return "App credentials ready — continue to sign in with Google."
        return "App credentials not imported yet."

    def _refresh_continue(self) -> None:
        self._status.setText(self._status_text())
        self._continue_btn.setEnabled(self._auth.has_client_secret())

    def _on_import(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select Google OAuth client JSON",
            str(Path.home() / "Downloads"),
            "JSON files (*.json);;All files (*.*)",
        )
        if not path_str:
            return
        try:
            saved = self._auth.import_client_secret(Path(path_str))
        except GoogleAuthError as exc:
            QMessageBox.warning(self, "Invalid Credentials File", str(exc))
            return
        self._refresh_continue()
        QMessageBox.information(
            self,
            "Credentials Saved",
            "App credentials were saved.\n\n"
            "Next: Continue to Google Sign-In — your browser will open so you "
            "can choose your Google account. Your login will be remembered.",
        )
        self._status.setText(f"Credentials saved. Ready to sign in. ({saved.name})")

    def _on_continue(self) -> None:
        if not self._auth.has_client_secret():
            QMessageBox.information(
                self,
                "Import Required",
                "Import the Desktop OAuth client JSON first, then continue.",
            )
            return
        self.accept()
