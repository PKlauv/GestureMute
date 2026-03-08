"""Floating status overlay for mic state indication (dot or pill variant)."""

import logging

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from gesturemute.gesture.gestures import MicState
from gesturemute.ui.theme import mic_state_color, COLOR_PAUSED, FONT_FAMILY

logger = logging.getLogger(__name__)

_DOT_SIZE = 36
_GLOW_SIZE = 48
_PILL_HEIGHT = 32
_PILL_PAD_H = 14
_PILL_DOT_SIZE = 8
_PILL_GAP = 8
_SCREEN_OFFSET = 50

_STATE_LABELS = {
    MicState.LIVE: "Live",
    MicState.MUTED: "Muted",
    MicState.LOCKED_MUTE: "Locked",
}
_PAUSED_LABEL = "Paused"


class StatusOverlay(QWidget):
    """Always-on-top draggable status overlay showing mic state."""

    def __init__(self) -> None:
        super().__init__()
        self._mic_state: MicState | None = MicState.LIVE
        self._color = QColor(mic_state_color(MicState.LIVE))
        self._style = "dot"
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._apply_size()
        self._move_to_default()

    def set_style(self, style: str) -> None:
        """Switch between 'dot' and 'pill' overlay variants.

        Args:
            style: Either 'dot' or 'pill'.
        """
        if style == self._style:
            return
        self._style = style
        self._apply_size()
        self.update()

    def _apply_size(self) -> None:
        """Resize widget based on current style."""
        if self._style == "pill":
            label = self._current_label()
            font = QFont("Inter", 11)
            font.setBold(True)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(label)
            width = _PILL_PAD_H + _PILL_DOT_SIZE + _PILL_GAP + text_w + _PILL_PAD_H
            self.setFixedSize(max(int(width), 80), _PILL_HEIGHT)
        else:
            self.setFixedSize(_GLOW_SIZE, _GLOW_SIZE)

    def _current_label(self) -> str:
        """Return the text label for the current state."""
        if self._mic_state is None:
            return _PAUSED_LABEL
        return _STATE_LABELS.get(self._mic_state, _PAUSED_LABEL)

    def _move_to_default(self) -> None:
        """Position at bottom-right of primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.right() - self.width() - _SCREEN_OFFSET,
            geo.bottom() - self.height() - _SCREEN_OFFSET,
        )

    def update_state(self, mic_state: MicState | None) -> None:
        """Update the overlay based on mic state.

        Args:
            mic_state: Current mic state, or None for paused/detection off.
        """
        self._mic_state = mic_state
        self._color = QColor(mic_state_color(mic_state))
        if self._style == "pill":
            self._apply_size()
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the current overlay variant."""
        if self._style == "pill":
            self._paint_pill()
        else:
            self._paint_dot()

    def _paint_dot(self) -> None:
        """Draw a glowing status dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = _GLOW_SIZE // 2
        cy = _GLOW_SIZE // 2

        # Outer glow
        glow = QColor(self._color)
        glow.setAlphaF(0.3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(0, 0, _GLOW_SIZE, _GLOW_SIZE)

        # Main dot
        offset = (_GLOW_SIZE - _DOT_SIZE) // 2
        painter.setBrush(self._color)
        painter.drawEllipse(offset, offset, _DOT_SIZE, _DOT_SIZE)

        painter.end()

    def _paint_pill(self) -> None:
        """Draw a pill-shaped indicator with dot + label."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background fill (state color at 12% opacity)
        bg = QColor(self._color)
        bg.setAlphaF(0.12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(0, 0, w, h, h // 2, h // 2)

        # Border (state color at 25% opacity)
        border = QColor(self._color)
        border.setAlphaF(0.25)
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, h // 2, h // 2)

        # Indicator dot with glow
        dot_x = _PILL_PAD_H
        dot_y = h // 2 - _PILL_DOT_SIZE // 2
        glow = QColor(self._color)
        glow.setAlphaF(0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(dot_x - 2, dot_y - 2, _PILL_DOT_SIZE + 4, _PILL_DOT_SIZE + 4)
        painter.setBrush(self._color)
        painter.drawEllipse(dot_x, dot_y, _PILL_DOT_SIZE, _PILL_DOT_SIZE)

        # Text label
        label = self._current_label()
        text_color = QColor(self._color)
        text_color.setAlphaF(0.9)
        painter.setPen(QPen(text_color))
        font = QFont("Inter", 11)
        font.setBold(True)
        painter.setFont(font)
        text_x = dot_x + _PILL_DOT_SIZE + _PILL_GAP
        painter.drawText(
            text_x, 0, w - text_x - _PILL_PAD_H, h,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

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
