"""Custom delegate that paints folder cards in a grid with clear status."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from src.upload.queue_model import QueueItemStatus, UploadQueueItem, format_bytes
from src.ui.styles import COLORS

# Status → (badge text, border, soft fill, badge fill, badge text color)
STATUS_STYLE: dict[QueueItemStatus, tuple[str, str, str, str, str]] = {
    QueueItemStatus.QUEUED: (
        "Waiting",
        "#c5d0db",
        "#f4f7fa",
        "#e8eef4",
        "#5a6b7a",
    ),
    QueueItemStatus.CANCELLED: (
        "Cancelled",
        "#c5d0db",
        "#f4f7fa",
        "#e8eef4",
        "#5a6b7a",
    ),
    QueueItemStatus.UPLOADING: (
        "Uploading",
        "#90c2f7",
        "#e8f1fc",
        "#1a73e8",
        "#ffffff",
    ),
    QueueItemStatus.DONE: (
        "Uploaded",
        "#9fd9b8",
        "#e4f7ec",
        "#0f9d58",
        "#ffffff",
    ),
    QueueItemStatus.FAILED: (
        "Failed",
        "#f0b4af",
        "#fdeceb",
        "#d93025",
        "#ffffff",
    ),
    QueueItemStatus.WATCHING: (
        "Syncing",
        "#9fd9b8",
        "#e8f7f1",
        "#0b8a6a",
        "#ffffff",
    ),
}


class FolderItemDelegate(QStyledItemDelegate):
    """Render each queue item as a grid folder card with obvious status."""

    CARD_WIDTH = 156
    CARD_HEIGHT = 168
    MARGIN = 6
    ICON_SIZE = 52

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        item: UploadQueueItem | None = index.data(Qt.ItemDataRole.UserRole)
        if item is None:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        status = item.status if isinstance(item.status, QueueItemStatus) else QueueItemStatus.QUEUED
        label, border_hex, fill_hex, badge_hex, badge_text_hex = STATUS_STYLE.get(
            status,
            STATUS_STYLE[QueueItemStatus.QUEUED],
        )
        if status == QueueItemStatus.UPLOADING and item.progress_percent:
            label = f"Uploading {item.progress_percent}%"

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        card = option.rect.adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)

        bg = QColor(fill_hex)
        border = QColor("#1a73e8" if selected else border_hex)
        border_width = 2 if selected else 1.5

        path = QPainterPath()
        path.addRoundedRect(QRectF(card), 14, 14)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, border_width))
        painter.drawPath(path)

        # Status badge (top)
        badge_font = QFont(painter.font())
        badge_font.setBold(True)
        badge_font.setPointSize(8)
        painter.setFont(badge_font)
        badge_width = max(64, painter.fontMetrics().horizontalAdvance(label) + 16)
        badge_rect = QRect(card.left() + 10, card.top() + 10, badge_width, 20)
        badge_path = QPainterPath()
        badge_path.addRoundedRect(QRectF(badge_rect), 8, 8)
        painter.fillPath(badge_path, QColor(badge_hex))
        painter.setPen(QColor(badge_text_hex))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)

        # Icon
        icon_rect = QRect(
            card.center().x() - self.ICON_SIZE // 2,
            card.top() + 40,
            self.ICON_SIZE,
            self.ICON_SIZE,
        )
        if item.is_file:
            self._paint_file_icon(painter, icon_rect, status)
        else:
            self._paint_folder_icon(painter, icon_rect, status)

        # Name
        name_rect = QRect(card.left() + 10, icon_rect.bottom() + 10, card.width() - 20, 22)
        name_font = QFont(painter.font())
        name_font.setBold(True)
        name_font.setPointSize(10)
        painter.setFont(name_font)
        painter.setPen(QColor(COLORS["ink"]))
        elided_name = painter.fontMetrics().elidedText(
            item.display_name,
            Qt.TextElideMode.ElideRight,
            name_rect.width(),
        )
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, elided_name)

        # Meta
        if item.is_file:
            meta = f"File · {format_bytes(item.total_bytes)}"
        else:
            meta = f"{item.file_count} files · {format_bytes(item.total_bytes)}"
        meta_rect = QRect(card.left() + 8, name_rect.bottom(), card.width() - 16, 18)
        meta_font = QFont(painter.font())
        meta_font.setBold(False)
        meta_font.setPointSize(8)
        painter.setFont(meta_font)
        painter.setPen(QColor(COLORS["ink_muted"]))
        painter.drawText(
            meta_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            meta,
        )

        # Progress bar for uploading
        if status == QueueItemStatus.UPLOADING:
            bar = QRect(card.left() + 14, card.bottom() - 14, card.width() - 28, 5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#d5e3f5"))
            painter.drawRoundedRect(bar, 3, 3)
            fill_w = max(4, int(bar.width() * max(0, min(100, item.progress_percent)) / 100))
            painter.setBrush(QColor(COLORS["primary"]))
            painter.drawRoundedRect(QRect(bar.left(), bar.top(), fill_w, bar.height()), 3, 3)

        painter.restore()

    def _paint_folder_icon(
        self,
        painter: QPainter,
        rect: QRect,
        status: QueueItemStatus,
    ) -> None:
        painter.save()
        if status == QueueItemStatus.DONE:
            tab_color, body_color, edge = "#7dcea0", "#0f9d58", "#0b7d46"
        elif status == QueueItemStatus.FAILED:
            tab_color, body_color, edge = "#f5b7b1", "#d93025", "#b3261e"
        elif status == QueueItemStatus.UPLOADING:
            tab_color, body_color, edge = "#a8cbf5", "#1a73e8", "#1557b0"
        elif status == QueueItemStatus.WATCHING:
            tab_color, body_color, edge = "#8fd4c0", "#0b8a6a", "#087057"
        else:
            tab_color, body_color, edge = "#f6c343", "#f4b400", "#e0a100"

        tab = QRectF(
            rect.left() + 2,
            rect.top() + 6,
            rect.width() * 0.42,
            rect.height() * 0.22,
        )
        body = QRectF(
            rect.left() + 2,
            rect.top() + rect.height() * 0.28,
            rect.width() - 4,
            rect.height() * 0.58,
        )
        tab_path = QPainterPath()
        tab_path.addRoundedRect(tab, 3, 3)
        body_path = QPainterPath()
        body_path.addRoundedRect(body, 5, 5)
        painter.fillPath(tab_path, QColor(tab_color))
        painter.fillPath(body_path, QColor(body_color))
        painter.setPen(QPen(QColor(edge), 1))
        painter.drawPath(body_path)

        highlight = QRectF(
            body.left() + 4,
            body.top() + 4,
            body.width() - 8,
            body.height() * 0.35,
        )
        painter.fillRect(highlight, QColor(255, 255, 255, 55))

        # Status mark on folder body
        mark_font = QFont(painter.font())
        mark_font.setBold(True)
        mark_font.setPointSize(11)
        painter.setFont(mark_font)
        painter.setPen(QColor("#ffffff"))
        mark = {
            QueueItemStatus.DONE: "✓",
            QueueItemStatus.FAILED: "!",
            QueueItemStatus.UPLOADING: "↑",
            QueueItemStatus.WATCHING: "↻",
            QueueItemStatus.QUEUED: "",
            QueueItemStatus.CANCELLED: "",
        }.get(status, "")
        if mark:
            painter.drawText(body.toRect(), Qt.AlignmentFlag.AlignCenter, mark)
        painter.restore()

    def _paint_file_icon(
        self,
        painter: QPainter,
        rect: QRect,
        status: QueueItemStatus,
    ) -> None:
        """Draw a simple document glyph, tinted by status."""
        painter.save()
        if status == QueueItemStatus.DONE:
            body, edge, fold = "#0f9d58", "#0b7d46", "#7dcea0"
        elif status == QueueItemStatus.FAILED:
            body, edge, fold = "#d93025", "#b3261e", "#f5b7b1"
        elif status == QueueItemStatus.UPLOADING:
            body, edge, fold = "#1a73e8", "#1557b0", "#a8cbf5"
        elif status == QueueItemStatus.WATCHING:
            body, edge, fold = "#0b8a6a", "#087057", "#8fd4c0"
        else:
            body, edge, fold = "#5b8def", "#3b6fd4", "#a8c4f5"

        page = QRectF(
            rect.left() + 8,
            rect.top() + 4,
            rect.width() - 16,
            rect.height() - 8,
        )
        path = QPainterPath()
        path.addRoundedRect(page, 4, 4)
        painter.fillPath(path, QColor(body))
        painter.setPen(QPen(QColor(edge), 1))
        painter.drawPath(path)

        # Folded corner
        fold_size = 10
        fold_path = QPainterPath()
        fold_path.moveTo(page.right() - fold_size, page.top())
        fold_path.lineTo(page.right(), page.top() + fold_size)
        fold_path.lineTo(page.right() - fold_size, page.top() + fold_size)
        fold_path.closeSubpath()
        painter.fillPath(fold_path, QColor(fold))

        # Text lines
        painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        y = page.top() + 16
        for _ in range(3):
            painter.drawLine(
                int(page.left() + 6),
                int(y),
                int(page.right() - 6),
                int(y),
            )
            y += 7

        mark_font = QFont(painter.font())
        mark_font.setBold(True)
        mark_font.setPointSize(10)
        painter.setFont(mark_font)
        painter.setPen(QColor("#ffffff"))
        mark = {
            QueueItemStatus.DONE: "✓",
            QueueItemStatus.FAILED: "!",
            QueueItemStatus.UPLOADING: "↑",
            QueueItemStatus.WATCHING: "↻",
        }.get(status, "")
        if mark:
            painter.drawText(page.toRect(), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, mark)
        painter.restore()
