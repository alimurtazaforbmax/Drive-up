"""Application factory."""

from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from src.auth.google_auth import GoogleAuth
from src.ui.main_window import MainWindow
from src.ui.styles import apply_app_font, build_stylesheet, load_app_font


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def create_app(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    configure_logging()
    app = QApplication(argv or sys.argv)
    app.setApplicationName("DriveUp")
    app.setOrganizationName("GoogleDriveProject")
    font_family = load_app_font()
    apply_app_font(app, font_family)
    app.setStyleSheet(build_stylesheet(font_family))
    window = MainWindow(auth=GoogleAuth())
    return app, window


def run() -> int:
    app, window = create_app()
    window.show()
    return app.exec()
