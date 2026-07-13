"""Application theme: colors, fonts, and stylesheet."""

from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase

COLORS = {
    "bg_top": "#e4f5ef",
    "bg_bottom": "#eef2f7",
    "surface": "#ffffff",
    "surface_muted": "#f4f8fb",
    "ink": "#132029",
    "ink_muted": "#607080",
    "accent": "#0f9d58",
    "accent_hover": "#0b7d46",
    "accent_soft": "#e4f7ec",
    "primary": "#1a73e8",
    "primary_hover": "#1557b0",
    "danger": "#d93025",
    "danger_hover": "#b3261e",
    "border": "#d5e1eb",
    "border_strong": "#b4c6d6",
}


def load_app_font() -> str:
    from src.config.paths import resource_root

    font_path = resource_root() / "assets" / "fonts" / "PlusJakartaSans.ttf"
    family = "Segoe UI"
    if font_path.is_file():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]
    return family


def apply_app_font(app, family: str) -> None:
    font = QFont(family, 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)


def build_stylesheet(font_family: str) -> str:
    c = COLORS
    return f"""
    * {{
        font-family: "{font_family}";
    }}

    QMainWindow {{
        background-color: {c["bg_bottom"]};
        color: {c["ink"]};
    }}

    QDialog {{
        background-color: {c["surface"]};
        color: {c["ink"]};
    }}

    QWidget#centralRoot {{
        background-color: transparent;
    }}

    QComboBox {{
        background: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 18px;
        color: {c["ink"]};
        font-weight: 600;
        font-size: 12px;
    }}
    QComboBox:hover {{
        border: 1px solid {c["border_strong"]};
    }}
    QComboBox:disabled {{
        color: #9aa8b5;
        background: {c["surface_muted"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {c["surface"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["accent_soft"]};
        selection-color: {c["ink"]};
        outline: none;
    }}

    QFrame#appHeader {{
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 14px;
    }}

    QLabel#compactMeta {{
        font-size: 11px;
        font-weight: 700;
        color: {c["ink_muted"]};
        letter-spacing: 0.4px;
    }}

    QPushButton#connectButton {{
        background-color: {c["accent"]};
        min-width: 88px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QPushButton#connectButton:hover {{
        background-color: {c["accent_hover"]};
    }}

    QPushButton#disconnectButton {{
        background-color: {c["surface"]};
        color: {c["danger"]};
        border: 1px solid #f0b4af;
        min-width: 88px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QPushButton#disconnectButton:hover {{
        background-color: #fdeceb;
        border: 1px solid {c["danger"]};
    }}
    QPushButton#disconnectButton:disabled {{
        color: #b7c0c9;
        border: 1px solid {c["border"]};
        background-color: {c["surface_muted"]};
    }}

    QPushButton#headerSecondary {{
        background-color: {c["surface_muted"]};
        color: {c["ink"]};
        border: 1px solid {c["border"]};
        padding: 8px 12px;
        font-size: 12px;
    }}
    QPushButton#headerSecondary:hover {{
        background-color: #e7eef5;
    }}
    QPushButton#headerSecondary:disabled {{
        color: #9aa8b5;
    }}

    QFrame#uploadPanel {{
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 18px;
    }}

    QFrame#dropZone {{
        background-color: {c["surface_muted"]};
        border: 2px dashed {c["border_strong"]};
        border-radius: 16px;
    }}

    QFrame#dropZone:hover {{
        background-color: #eaf6f0;
        border: 2px dashed {c["accent"]};
    }}

    QFrame#panelFrame {{
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 14px;
    }}

    QLabel#brandLabel {{
        font-size: 22px;
        font-weight: 800;
        color: {c["ink"]};
        letter-spacing: -0.6px;
    }}

    QLabel#brandAccent {{
        font-size: 22px;
        font-weight: 800;
        color: {c["accent"]};
    }}

    QLabel#headerHint {{
        font-size: 12px;
        color: {c["ink_muted"]};
    }}

    QLabel#titleLabel {{
        font-size: 20px;
        font-weight: 700;
        color: {c["ink"]};
    }}

    QLabel#subtitleLabel {{
        font-size: 13px;
        color: {c["ink_muted"]};
    }}

    QLabel#sectionTitle {{
        font-size: 15px;
        font-weight: 700;
        color: {c["ink"]};
    }}

    QLabel#metaLabel {{
        font-size: 12px;
        color: {c["ink_muted"]};
    }}

    QLabel#statusDot {{
        font-size: 14px;
        font-weight: 700;
        color: #9aa8b5;
    }}

    QLabel#statusDot[connected="true"] {{
        color: {c["accent"]};
    }}

    QLabel#statusTitle {{
        font-size: 14px;
        font-weight: 700;
        color: {c["ink"]};
    }}

    QLabel#statusDetail {{
        font-size: 12px;
        color: {c["ink_muted"]};
    }}

    QLabel#destPill {{
        font-size: 13px;
        font-weight: 600;
        color: {c["ink"]};
        background-color: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        padding: 10px 14px;
    }}

    QLabel#dropTitle {{
        font-size: 18px;
        font-weight: 700;
        color: {c["ink"]};
    }}

    QLabel#dropSubtitle {{
        font-size: 13px;
        color: {c["ink_muted"]};
    }}

    QLabel#queueCount {{
        font-size: 12px;
        font-weight: 600;
        color: {c["accent"]};
        background-color: {c["accent_soft"]};
        border-radius: 8px;
        padding: 4px 10px;
    }}

    QPushButton {{
        background-color: {c["primary"]};
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 16px;
        font-weight: 650;
        font-size: 13px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {c["primary_hover"]};
    }}
    QPushButton:disabled {{
        background-color: #c8d3de;
        color: #f8fafc;
    }}

    QPushButton#connectButton {{
        background-color: {c["accent"]};
        min-width: 120px;
        padding: 11px 18px;
    }}
    QPushButton#connectButton:hover {{
        background-color: {c["accent_hover"]};
    }}

    QPushButton#disconnectButton {{
        background-color: {c["surface"]};
        color: {c["danger"]};
        border: 1px solid #f0b4af;
        min-width: 110px;
        padding: 11px 18px;
    }}
    QPushButton#disconnectButton:hover {{
        background-color: #fdeceb;
        border: 1px solid {c["danger"]};
    }}
    QPushButton#disconnectButton:disabled {{
        color: #b7c0c9;
        border: 1px solid {c["border"]};
        background-color: {c["surface_muted"]};
    }}

    QPushButton#primaryCta {{
        background-color: {c["accent"]};
        padding: 12px 22px;
        font-size: 14px;
        min-width: 140px;
    }}
    QPushButton#primaryCta:hover {{
        background-color: {c["accent_hover"]};
    }}

    QPushButton#secondaryButton {{
        background-color: {c["surface"]};
        color: {c["ink"]};
        border: 1px solid {c["border"]};
    }}
    QPushButton#secondaryButton:hover {{
        background-color: {c["surface_muted"]};
        border: 1px solid {c["border_strong"]};
    }}

    QPushButton#dangerButton {{
        background-color: {c["danger"]};
    }}
    QPushButton#dangerButton:hover {{
        background-color: {c["danger_hover"]};
    }}

    QPushButton#ghostButton {{
        background-color: transparent;
        color: {c["primary"]};
        border: 1px solid transparent;
    }}
    QPushButton#ghostButton:hover {{
        background-color: {c["surface_muted"]};
        border: 1px solid {c["border"]};
    }}

    QPushButton#addDriveButton {{
        background-color: {c["primary"]};
        color: white;
        border: none;
        min-width: 88px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QPushButton#addDriveButton:hover {{
        background-color: {c["primary_hover"]};
    }}
    QPushButton#addDriveButton:disabled {{
        background-color: #c8d3de;
        color: #f8fafc;
    }}

    QPushButton#addFoldersButton {{
        background-color: {c["accent"]};
        color: white;
        border: none;
    }}
    QPushButton#addFoldersButton:hover {{
        background-color: {c["accent_hover"]};
    }}

    QPushButton#removeButton {{
        background-color: #fdeceb;
        color: {c["danger"]};
        border: 1px solid #f0b4af;
    }}
    QPushButton#removeButton:hover {{
        background-color: #fad2cf;
        border: 1px solid {c["danger"]};
    }}

    QPushButton#retryButton {{
        background-color: #fff3cd;
        color: #8a6d00;
        border: 1px solid #f0d78c;
    }}
    QPushButton#retryButton:hover {{
        background-color: #ffe8a3;
        border: 1px solid #e0b800;
    }}

    QListView#folderList {{
        background: transparent;
        border: none;
        outline: none;
        padding: 4px;
    }}
    QListView#folderList::item {{
        border: none;
        padding: 0;
    }}

    QPlainTextEdit {{
        background: #12202c;
        color: #d7e8df;
        border: 1px solid #1e3344;
        border-radius: 12px;
        padding: 10px;
        font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
        font-size: 12px;
        selection-background-color: #0f9d58;
    }}

    QProgressBar {{
        border: 1px solid {c["border"]};
        border-radius: 10px;
        text-align: center;
        background: {c["surface"]};
        color: {c["ink"]};
        font-weight: 600;
        height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c["accent"]},
            stop:1 {c["primary"]}
        );
        border-radius: 9px;
    }}

    QLineEdit {{
        background: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 8px 10px;
    }}
    QLineEdit:focus {{
        border: 1px solid {c["primary"]};
    }}

    QListWidget {{
        background: {c["surface"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 8px;
        margin: 2px;
    }}
    QListWidget::item:selected {{
        background: {c["accent_soft"]};
        color: {c["ink"]};
    }}
    QListWidget::item:hover {{
        background: {c["surface_muted"]};
    }}

    QCheckBox {{
        spacing: 10px;
        color: {c["ink"]};
        font-weight: 500;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid {c["border_strong"]};
        background: {c["surface"]};
    }}
    QCheckBox::indicator:checked {{
        background: {c["accent"]};
        border: 1px solid {c["accent"]};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: #b7c9d8;
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QDialogButtonBox QPushButton {{
        min-width: 100px;
    }}
    """


APP_STYLESHEET = build_stylesheet("Segoe UI")
