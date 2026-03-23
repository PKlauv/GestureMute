"""Floating status overlay for mic state indication (dot, pill, or bar variant)."""

import logging

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from gesturemute.config import Config
from gesturemute.gesture.gestures import MicState
from gesturemute.ui.theme import mic_state_color, ACCENT, FONT_FAMILY, SURFACE

logger = logging.getLogger(__name__)

_DOT_SIZE_BASE = 36
_GLOW_SIZE_BASE = 48
_PILL_HEIGHT_BASE = 32
_PILL_PAD_H_BASE = 14
_PILL_DOT_SIZE_BASE = 8
_PILL_GAP_BASE = 8
_BAR_HEIGHT_BASE = 24
_BAR_MIN_WIDTH_BASE = 100
_BAR_PAD_H_BASE = 16
_BAR_ACCENT_HEIGHT_BASE = 3
_SCREEN_OFFSET = 50

_STATE_LABELS = {
    MicState.LIVE: "Live",
    MicState.MUTED: "Muted",
    MicState.LOCKED_MUTE: "Locked",
}
_PAUSED_LABEL = "Paused"
_LOADING_LABEL = "Loading..."


class StatusOverlay(QWidget):
    """Always-on-top draggable status overlay showing mic state."""

    clicked = pyqtSignal()
    toggle_detection_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    preview_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, style: str = "dot") -> None:
        super().__init__()
        self._mic_state: MicState | None = MicState.LIVE
        self._loading = True
        self._color = QColor(ACCENT)
        self._style = style
        self._drag_pos: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dpi_scale = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._update_dpi_scale()
        self._apply_size()
        self._move_to_default()

        # Right-click context menu
        self._context_menu = QMenu()
        self._toggle_action = QAction("Pause Detection")
        self._toggle_action.triggered.connect(self.toggle_detection_requested.emit)
        self._context_menu.addAction(self._toggle_action)
        self._context_menu.addSeparator()
        self._settings_action = QAction("Settings...")
        self._settings_action.triggered.connect(self.settings_requested.emit)
        self._context_menu.addAction(self._settings_action)
        self._preview_action = QAction("Preview")
        self._preview_action.triggered.connect(self.preview_requested.emit)
        self._context_menu.addAction(self._preview_action)
        self._context_menu.addSeparator()
        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._context_menu.addAction(self._quit_action)

    def _update_dpi_scale(self) -> None:
        """Read the device pixel ratio from the current screen."""
        screen = self.screen()
        if screen is not None:
            self._dpi_scale = screen.devicePixelRatio()
        else:
            self._dpi_scale = 1.0

    def _s(self, base: int) -> int:
        """Scale a base pixel value by the current DPI factor."""
        return max(1, int(base * self._dpi_scale))

    def update_toggle_label(self, detection_active: bool) -> None:
        """Update the context menu toggle action text."""
        self._toggle_action.setText(
            "Pause Detection" if detection_active else "Resume Detection"
        )

    def set_style(self, style: str) -> None:
        """Switch between 'dot', 'pill', and 'bar' overlay variants.

        Args:
            style: One of 'dot', 'pill', or 'bar'.
        """
        if style == self._style:
            return
        self._style = style
        self._apply_size()
        self._clamp_to_screen()
        self.update()

    def _apply_size(self) -> None:
        """Resize widget based on current style, scaled for DPI."""
        if self._style == "pill":
            label = self._current_label()
            font = QFont("Inter", 11)
            font.setBold(True)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(label)
            pad_h = self._s(_PILL_PAD_H_BASE)
            dot_sz = self._s(_PILL_DOT_SIZE_BASE)
            gap = self._s(_PILL_GAP_BASE)
            width = pad_h + dot_sz + gap + text_w + pad_h
            self.setFixedSize(max(int(width), self._s(80)), self._s(_PILL_HEIGHT_BASE))
        elif self._style == "bar":
            label = self._current_label()
            font = QFont(FONT_FAMILY, 9)
            font.setBold(True)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(label)
            pad_h = self._s(_BAR_PAD_H_BASE)
            width = pad_h + text_w + pad_h
            self.setFixedSize(max(int(width), self._s(_BAR_MIN_WIDTH_BASE)), self._s(_BAR_HEIGHT_BASE))
        else:
            glow = self._s(_GLOW_SIZE_BASE)
            self.setFixedSize(glow, glow)

    def _current_label(self) -> str:
        """Return the text label for the current state."""
        if self._loading:
            return _LOADING_LABEL
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

    def _clamp_to_screen(self) -> None:
        """Clamp the overlay position to the visible screen area."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = max(geo.left(), min(self.x(), geo.right() - self.width()))
        y = max(geo.top(), min(self.y(), geo.bottom() - self.height()))
        self.move(x, y)

    def restore_position(self, config: Config) -> None:
        """Restore saved overlay position, or fall back to default.

        Args:
            config: App config with optional overlay_x/overlay_y.
        """
        if config.overlay_x is None or config.overlay_y is None:
            self._move_to_default()
            return
        self.move(config.overlay_x, config.overlay_y)
        self._clamp_to_screen()

    def set_ready(self) -> None:
        """Clear the loading state and show the current mic state."""
        if not self._loading:
            return
        self._loading = False
        self._color = QColor(mic_state_color(self._mic_state))
        if self._style in ("pill", "bar"):
            self._apply_size()
        self.update()

    def update_state(self, mic_state: MicState | None) -> None:
        """Update the overlay based on mic state.

        Args:
            mic_state: Current mic state, or None for paused/detection off.
        """
        self._mic_state = mic_state
        if not self._loading:
            self._color = QColor(mic_state_color(mic_state))
        if self._style in ("pill", "bar"):
            self._apply_size()
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the current overlay variant."""
        if self._style == "pill":
            self._paint_pill()
        elif self._style == "bar":
            self._paint_bar()
        else:
            self._paint_dot()

    def _paint_dot(self) -> None:
        """Draw a glowing status dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        glow_sz = self._s(_GLOW_SIZE_BASE)
        dot_sz = self._s(_DOT_SIZE_BASE)

        # Outer glow
        glow = QColor(self._color)
        glow.setAlphaF(0.3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(0, 0, glow_sz, glow_sz)

        # Main dot
        offset = (glow_sz - dot_sz) // 2
        painter.setBrush(self._color)
        painter.drawEllipse(offset, offset, dot_sz, dot_sz)

        painter.end()

    def _paint_pill(self) -> None:
        """Draw a pill-shaped indicator with dot + label."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        pad_h = self._s(_PILL_PAD_H_BASE)
        dot_sz = self._s(_PILL_DOT_SIZE_BASE)
        gap = self._s(_PILL_GAP_BASE)

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
        dot_x = pad_h
        dot_y = h // 2 - dot_sz // 2
        glow = QColor(self._color)
        glow.setAlphaF(0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(dot_x - 2, dot_y - 2, dot_sz + 4, dot_sz + 4)
        painter.setBrush(self._color)
        painter.drawEllipse(dot_x, dot_y, dot_sz, dot_sz)

        # Text label
        label = self._current_label()
        text_color = QColor(self._color)
        text_color.setAlphaF(0.9)
        painter.setPen(QPen(text_color))
        font = QFont("Inter", 11)
        font.setBold(True)
        painter.setFont(font)
        text_x = dot_x + dot_sz + gap
        painter.drawText(
            text_x, 0, w - text_x - pad_h, h,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        painter.end()

    def _paint_bar(self) -> None:
        """Draw a slim glass bar with a glowing accent line at the bottom."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        accent_h = self._s(_BAR_ACCENT_HEIGHT_BASE)

        # Frosted dark background (~85% opacity)
        bg = QColor(SURFACE)
        bg.setAlphaF(0.85)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        # Centered label text in state color
        label = self._current_label()
        text_color = QColor(self._color)
        text_color.setAlphaF(0.9)
        painter.setPen(QPen(text_color))
        font = QFont(FONT_FAMILY, 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            0, 0, w, h - accent_h,
            Qt.AlignmentFlag.AlignCenter,
            label,
        )

        # Bottom accent line with glow
        accent_y = h - accent_h
        glow = QColor(self._color)
        glow.setAlphaF(0.35)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawRoundedRect(2, accent_y - 1, w - 4, accent_h + 2, 2, 2)

        painter.setBrush(self._color)
        painter.drawRoundedRect(3, accent_y, w - 6, accent_h, 2, 2)

        painter.end()

    def contextMenuEvent(self, event) -> None:
        """Show right-click context menu."""
        self._context_menu.exec(event.globalPos())

    def mousePressEvent(self, event) -> None:
        """Start drag on left click, record press position for click detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_pos = self._press_pos - self.pos()

    def mouseMoveEvent(self, event) -> None:
        """Move overlay while dragging."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        """End drag. If barely moved, treat as click. Clamp to screen bounds."""
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            delta = event.globalPosition().toPoint() - self._press_pos
            if abs(delta.x()) + abs(delta.y()) < 5:
                self.clicked.emit()
            else:
                self._clamp_to_screen()
        self._drag_pos = None
        self._press_pos = None
