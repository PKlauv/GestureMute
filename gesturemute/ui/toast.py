"""Toast notifications for gesture feedback."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QFont
from PyQt6.QtWidgets import QApplication, QWidget

from gesturemute.config import Config
from gesturemute.gesture.gestures import MicState
from gesturemute.ui.overlay import StatusOverlay
from gesturemute.ui.theme import (
    ACCENT, ACCENT_LIGHT, TEXT_PRIMARY, TEXT_DIM, SURFACE,
    mic_state_color,
)

logger = logging.getLogger(__name__)

_TOAST_WIDTH = 280
_TOAST_HEIGHT = 64
_ACCENT_WIDTH = 4
_CORNER_RADIUS = 12
_FADE_IN_MS = 100
_FADE_OUT_MS = 300
_ICON_SIZE = 36

_ACTION_TEXT: dict[str, tuple[str, str]] = {
    "mute": ("Microphone Muted", "Open palm detected"),
    "unmute": ("Microphone Live", "Hand released"),
    "lock_mute": ("Mute Locked", "Palm to fist"),
    "unlock_mute": ("Mute Unlocked", "Fist to palm"),
    "volume_up": ("Volume Up", "Thumbs up"),
    "volume_down": ("Volume Down", "Thumbs down"),
    "pause_detection": ("Detection Paused", "Two fists detected"),
}


class ToastNotification(QWidget):
    """Frameless, translucent toast that shows gesture action feedback."""

    def __init__(
        self, title: str, subtitle: str, accent_color: str, duration_ms: int,
        volume_value: int | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._subtitle = subtitle
        self._accent_color = QColor(accent_color)
        self._duration_ms = duration_ms
        self._volume_value = volume_value

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        height = _TOAST_HEIGHT + (20 if volume_value is not None else 0)
        self.setFixedSize(_TOAST_WIDTH, height)

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

        self.on_finished: Callable[[], None] | None = None

    def show_animated(self) -> None:
        """Show the toast with fade-in animation and schedule auto-dismiss."""
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_in_anim.start()
        self._dismiss_timer.start(self._duration_ms)

    def update_volume(self, new_value: int) -> None:
        """Update the volume bar and percentage in place without animation restart.

        Args:
            new_value: New volume level 0-100.
        """
        self._volume_value = new_value
        self._subtitle = f"{new_value}%"
        self.update()

    def reset_dismiss_timer(self, duration_ms: int) -> None:
        """Restart the auto-dismiss countdown.

        Args:
            duration_ms: Milliseconds before the toast auto-dismisses.
        """
        self._dismiss_timer.stop()
        self._dismiss_timer.start(duration_ms)

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
        """Draw dark rounded rect with accent bar, icon area, and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background: dark surface at 95% opacity
        bg = QColor(SURFACE)
        bg.setAlphaF(0.95)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect(), _CORNER_RADIUS, _CORNER_RADIUS)

        # Subtle border
        border = QColor(255, 255, 255, 15)
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, _CORNER_RADIUS, _CORNER_RADIUS)

        # Left accent bar
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._accent_color)
        painter.drawRoundedRect(0, 0, _ACCENT_WIDTH + _CORNER_RADIUS, h, _CORNER_RADIUS, _CORNER_RADIUS)
        painter.drawRect(_ACCENT_WIDTH, 0, _CORNER_RADIUS, h)

        content_x = _ACCENT_WIDTH + 14

        # Icon area: rounded square with state-colored bg at 12%
        icon_bg = QColor(self._accent_color)
        icon_bg.setAlphaF(0.12)
        icon_y = 14
        painter.setBrush(icon_bg)
        painter.drawRoundedRect(content_x, icon_y, _ICON_SIZE, _ICON_SIZE, 8, 8)

        # Icon: draw a small colored dot in the center as indicator
        painter.setBrush(self._accent_color)
        dot_r = 6
        painter.drawEllipse(
            content_x + _ICON_SIZE // 2 - dot_r,
            icon_y + _ICON_SIZE // 2 - dot_r,
            dot_r * 2, dot_r * 2,
        )

        # Title text
        text_x = content_x + _ICON_SIZE + 12
        painter.setPen(QPen(QColor(TEXT_PRIMARY)))
        title_font = QFont("Inter", 11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            text_x, icon_y - 1, w - text_x - 16, 20,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._title,
        )

        # Subtitle text
        painter.setPen(QPen(QColor(TEXT_DIM)))
        sub_font = QFont("Inter", 9)
        painter.setFont(sub_font)
        painter.drawText(
            text_x, icon_y + 19, w - text_x - 16, 18,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._subtitle,
        )

        # Clip to toast shape so volume bar elements don't overflow rounded corners
        clip_path = QPainterPath()
        clip_path.addRoundedRect(0, 0, float(w), float(h), _CORNER_RADIUS, _CORNER_RADIUS)
        painter.setClipPath(clip_path)

        # Volume bar (if present)
        if self._volume_value is not None:
            bar_y = _TOAST_HEIGHT + 4
            bar_x = _ACCENT_WIDTH + 14
            bar_w = w - bar_x - 14
            bar_h = 8

            # Track
            track_color = QColor(255, 255, 255, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(track_color)
            painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)

            # Fill with gradient
            fill_w = max(int(bar_w * self._volume_value / 100), 2)
            grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            grad.setColorAt(0.0, QColor(ACCENT))
            grad.setColorAt(1.0, QColor(ACCENT_LIGHT))
            painter.setBrush(grad)
            painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 4, 4)

            # Slider handle circle at fill edge
            handle_r = 6
            handle_cx = bar_x + handle_r + int((bar_w - 2 * handle_r) * self._volume_value / 100)
            handle_cy = bar_y + bar_h // 2
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawEllipse(
                handle_cx - handle_r, handle_cy - handle_r,
                handle_r * 2, handle_r * 2,
            )

            # Volume percentage text
            painter.setPen(QPen(QColor(ACCENT_LIGHT)))
            pct_font = QFont("Inter", 10)
            pct_font.setBold(True)
            painter.setFont(pct_font)
            painter.drawText(
                w - 60, icon_y - 1, 44, 20,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{self._volume_value}%",
            )

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
        self._is_volume_toast: bool = False

    def show_toast(
        self, action: str, mic_state: MicState, value: int = 0,
    ) -> None:
        """Show a toast notification for the given action.

        Replaces any existing toast. Positions above the status dot overlay.

        Args:
            action: Action key (e.g. "mute", "unmute", "volume_up").
            mic_state: Current mic state for accent color.
            value: Volume level (0-100) for volume actions.
        """
        text_pair = _ACTION_TEXT.get(action)
        if text_pair is None:
            return

        title, subtitle = text_pair
        accent = mic_state_color(mic_state)
        is_volume = action in ("volume_up", "volume_down")
        volume_value = value if is_volume else None

        # Update subtitle with actual percentage for volume
        if is_volume and value:
            subtitle = f"{value}%"

        # Reuse existing volume toast for smooth updates without flicker
        if is_volume and self._is_volume_toast and self._current_toast is not None:
            try:
                self._current_toast.update_volume(volume_value)
                self._current_toast.reset_dismiss_timer(1000)
                logger.debug("Toast updated: %s - %s", title, subtitle)
                return
            except RuntimeError:
                self._current_toast = None
                self._is_volume_toast = False

        # Replace existing toast
        if self._current_toast is not None:
            try:
                self._current_toast.dismiss()
            except RuntimeError:
                pass
            self._current_toast = None

        self._is_volume_toast = is_volume

        toast = ToastNotification(
            title, subtitle, accent,
            1000 if is_volume else self._config.toast_duration_ms,
            volume_value=volume_value,
        )
        toast.on_finished = self._on_toast_finished
        self._current_toast = toast

        # Position above the overlay
        overlay_pos = self._overlay.pos()
        toast_x = overlay_pos.x() + self._overlay.width() // 2 - _TOAST_WIDTH // 2
        toast_y = overlay_pos.y() - toast.height() - 10

        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            toast_x = max(geo.left(), min(toast_x, geo.right() - toast.width()))
            toast_y = max(geo.top(), min(toast_y, geo.bottom() - toast.height()))

        toast.move(toast_x, toast_y)

        toast.show_animated()
        logger.debug("Toast shown: %s - %s", title, subtitle)

    def _on_toast_finished(self) -> None:
        """Clear reference when a toast auto-dismisses."""
        self._current_toast = None
        self._is_volume_toast = False
