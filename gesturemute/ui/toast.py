"""Toast notifications for gesture feedback."""

import logging

from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import QWidget

from gesturemute.config import Config
from gesturemute.gesture.gestures import MicState
from gesturemute.ui.overlay import StatusOverlay

logger = logging.getLogger(__name__)

_TOAST_WIDTH = 220
_TOAST_HEIGHT = 50
_ACCENT_WIDTH = 5
_CORNER_RADIUS = 10
_FADE_IN_MS = 100
_FADE_OUT_MS = 300

_ACCENT_COLORS = {
    MicState.LIVE: "#10B981",
    MicState.MUTED: "#E94560",
    MicState.LOCKED_MUTE: "#E94560",
}

_ACTION_TEXT = {
    "mute": "Muted",
    "unmute": "Unmuted",
    "lock_mute": "Mute Locked",
    "unlock_mute": "Unlocked",
    "volume_up": "Volume +5%",
    "volume_down": "Volume -5%",
}


class ToastNotification(QWidget):
    """Frameless, translucent toast that shows gesture action feedback."""

    def __init__(self, text: str, accent_color: str, duration_ms: int) -> None:
        super().__init__()
        self._text = text
        self._accent_color = QColor(accent_color)
        self._duration_ms = duration_ms

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(_TOAST_WIDTH, _TOAST_HEIGHT)

        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in_anim.setDuration(_FADE_IN_MS)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out_anim.setDuration(_FADE_OUT_MS)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.finished.connect(self._on_fade_out_done)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_fade_out)

        self.on_finished: callable | None = None

    def show_animated(self) -> None:
        """Show the toast with fade-in animation and schedule auto-dismiss."""
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_in_anim.start()
        self._dismiss_timer.start(self._duration_ms)

    def dismiss(self) -> None:
        """Immediately stop timers and hide."""
        self._dismiss_timer.stop()
        self._fade_in_anim.stop()
        self._fade_out_anim.stop()
        self.hide()
        self.deleteLater()

    def _start_fade_out(self) -> None:
        """Begin fade-out animation."""
        self._fade_out_anim.start()

    def _on_fade_out_done(self) -> None:
        """Clean up after fade-out completes."""
        self.hide()
        if self.on_finished is not None:
            self.on_finished()
        self.deleteLater()

    def paintEvent(self, event) -> None:
        """Draw translucent rounded rect with colored accent bar and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background: semi-transparent white
        bg = QColor("#FFFFFF")
        bg.setAlphaF(0.95)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect(), _CORNER_RADIUS, _CORNER_RADIUS)

        # Left accent bar
        painter.setBrush(self._accent_color)
        painter.drawRoundedRect(0, 0, _ACCENT_WIDTH + _CORNER_RADIUS, _TOAST_HEIGHT, _CORNER_RADIUS, _CORNER_RADIUS)
        painter.drawRect(_ACCENT_WIDTH, 0, _CORNER_RADIUS, _TOAST_HEIGHT)

        # Text
        painter.setPen(QPen(QColor("#1A1A2E")))
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        painter.setFont(font)
        text_rect = self.rect().adjusted(_ACCENT_WIDTH + 15, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)

        painter.end()


class ToastManager:
    """Manages toast lifecycle: positioning, replacement, and timing.

    Args:
        overlay: StatusOverlay to position toasts relative to.
        config: App config for toast duration.
    """

    def __init__(self, overlay: StatusOverlay, config: Config) -> None:
        self._overlay = overlay
        self._config = config
        self._current_toast: ToastNotification | None = None

    def show_toast(self, action: str, mic_state: MicState) -> None:
        """Show a toast notification for the given action.

        Replaces any existing toast. Positions above the status dot overlay.

        Args:
            action: Action key (e.g. "mute", "unmute", "volume_up").
            mic_state: Current mic state for accent color.
        """
        text = _ACTION_TEXT.get(action)
        if text is None:
            return

        accent = _ACCENT_COLORS.get(mic_state, "#9CA3AF")

        # Replace existing toast
        if self._current_toast is not None:
            try:
                self._current_toast.dismiss()
            except RuntimeError:
                pass
            self._current_toast = None

        toast = ToastNotification(text, accent, self._config.toast_duration_ms)
        toast.on_finished = self._on_toast_finished
        self._current_toast = toast

        # Position above the overlay dot
        overlay_pos = self._overlay.pos()
        toast_x = overlay_pos.x() + self._overlay.width() // 2 - _TOAST_WIDTH // 2
        toast_y = overlay_pos.y() - _TOAST_HEIGHT - 10
        toast.move(toast_x, toast_y)

        toast.show_animated()
        logger.debug("Toast shown: %s", text)

    def _on_toast_finished(self) -> None:
        """Clear reference when a toast auto-dismisses."""
        self._current_toast = None
