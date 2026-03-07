"""Floating status dot overlay for mic state indication."""

import logging

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from gesturemute.gesture.gestures import MicState

logger = logging.getLogger(__name__)

# Design token colors
_COLORS = {
    MicState.LIVE: "#10B981",
    MicState.MUTED: "#E94560",
    MicState.LOCKED_MUTE: "#E94560",
}
_COLOR_PAUSED = "#9CA3AF"

_DOT_SIZE = 36
_SCREEN_OFFSET = 50


class StatusOverlay(QWidget):
    """Always-on-top draggable status dot showing mic state."""

    def __init__(self) -> None:
        super().__init__()
        self._color = QColor(_COLORS[MicState.LIVE])
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_DOT_SIZE, _DOT_SIZE)
        self._move_to_default()

    def _move_to_default(self) -> None:
        """Position at bottom-right of primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.right() - _DOT_SIZE - _SCREEN_OFFSET,
            geo.bottom() - _DOT_SIZE - _SCREEN_OFFSET,
        )

    def update_state(self, mic_state: MicState | None) -> None:
        """Update the dot color based on mic state.

        Args:
            mic_state: Current mic state, or None for paused/detection off.
        """
        if mic_state is None:
            self._color = QColor(_COLOR_PAUSED)
        else:
            self._color = QColor(_COLORS.get(mic_state, _COLOR_PAUSED))
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the status dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.setBrush(self._color)
        painter.drawEllipse(1, 1, _DOT_SIZE - 2, _DOT_SIZE - 2)
        painter.end()

    def mousePressEvent(self, event) -> None:
        """Start drag on left click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        """Move overlay while dragging."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        """End drag."""
        self._drag_pos = None
