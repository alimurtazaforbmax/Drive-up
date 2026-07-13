"""Painted gradient backdrop for the main window."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PyQt6.QtWidgets import QWidget

from src.ui.styles import COLORS


class GradientBackground(QWidget):
    """Soft top-to-bottom wash so the UI is not a flat slab."""

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(QPointF(0, 0), QPointF(0, self.height()))
        gradient.setColorAt(0.0, QColor(COLORS["bg_top"]))
        gradient.setColorAt(0.55, QColor("#eaf3f7"))
        gradient.setColorAt(1.0, QColor(COLORS["bg_bottom"]))
        painter.fillRect(self.rect(), gradient)

        # Soft corner bloom for depth (subtle, not neon glow)
        bloom = QLinearGradient(QPointF(self.width(), 0), QPointF(self.width() * 0.4, self.height() * 0.45))
        bloom.setColorAt(0.0, QColor(15, 157, 88, 38))
        bloom.setColorAt(1.0, QColor(15, 157, 88, 0))
        painter.fillRect(self.rect(), bloom)

        bloom2 = QLinearGradient(QPointF(0, self.height()), QPointF(self.width() * 0.55, self.height() * 0.35))
        bloom2.setColorAt(0.0, QColor(26, 115, 232, 28))
        bloom2.setColorAt(1.0, QColor(26, 115, 232, 0))
        painter.fillRect(self.rect(), bloom2)

        super().paintEvent(event)
