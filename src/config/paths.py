"""Resolve app/resource roots for both source runs and frozen installers."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """
    Read-only bundled assets (fonts, etc.).

    PyInstaller extracts these under sys._MEIPASS.
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def app_root() -> Path:
    """
    Writable / adjacent app directory.

    Next to the executable when frozen; project root in development.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
