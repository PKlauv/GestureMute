"""HUD-style dashboard preview window with live gesture monitoring."""

import collections
import time

import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot, QRectF
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from gesturemute.gesture.gestures import (
    Gesture,
    GestureScores,
    GestureState,
    HandLandmarks,
    HAND_CONNECTIONS,
)
from gesturemute.ui.theme import (
    ACCENT,
    ACCENT_LIGHT,
    BACKGROUND,
    COLOR_LIVE,
    COLOR_LOCKED,
    COLOR_MUTED,
    COLOR_PAUSED,
    FONT_FAMILY,
    SURFACE,
    TEXT_DIM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

# State pill color mapping
_STATE_COLORS: dict[GestureState, str] = {
    GestureState.IDLE: TEXT_DIM,
    GestureState.PALM_HOLD: COLOR_MUTED,
    GestureState.MUTE_LOCKED: COLOR_LOCKED,
    GestureState.FIST_PENDING_UNLOCK: COLOR_LOCKED,
    GestureState.VOLUME_UP: ACCENT,
    GestureState.VOLUME_DOWN: ACCENT,
}

# Display labels for gesture bars
_BAR_LABELS: list[tuple[str, str]] = [
    ("Open_Palm", "Open Palm"),
    ("Closed_Fist", "Closed Fist"),
    ("Thumb_Up", "Thumb Up"),
    ("Thumb_Down", "Thumb Down"),
    ("None", "None"),
]


class CameraCanvas(QWidget):
    """Custom widget that draws the camera feed with HUD overlays via QPainter."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 480)
        self._image: QImage | None = None
        self._scaled: QImage | None = None
        self._x_off: int = 0
        self._y_off: int = 0
        self._cached_size: tuple[int, int] = (0, 0)
        self._landmarks: HandLandmarks | None = None
        self._active_gesture: str = ""
        self._active_confidence: float = 0.0
        self._fps: float = 0.0
        self._handedness: str = ""

    def set_image(self, image: QImage) -> None:
        """Set the camera frame image, pre-scaling for paint performance."""
        self._image = image
        w, h = self.width(), self.height()
        self._scaled = image.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._x_off = (w - self._scaled.width()) // 2
        self._y_off = (h - self._scaled.height()) // 2
        self._cached_size = (w, h)
        self.update()

    def set_landmarks(self, landmarks: HandLandmarks | None) -> None:
        """Set hand landmark data for overlay drawing."""
        self._landmarks = landmarks

    def set_active_gesture(self, name: str, confidence: float) -> None:
        """Set the active gesture pill text."""
        self._active_gesture = name
        self._active_confidence = confidence

    def set_fps(self, fps: float) -> None:
        """Set the FPS value for the badge."""
        self._fps = fps

    def set_handedness(self, handedness: str) -> None:
        """Set the handedness badge text."""
        self._handedness = handedness

    def clear_frame(self) -> None:
        """Reset all image and overlay state, triggering a NO SIGNAL repaint."""
        self._image = None
        self._scaled = None
        self._landmarks = None
        self._active_gesture = ""
        self._active_confidence = 0.0
        self._fps = 0.0
        self._handedness = ""
        self.update()

    def paintEvent(self, event) -> None:
        """Draw camera frame and all HUD overlays."""
        p = QPainter(self)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(BACKGROUND))

        if self._scaled is not None:
            # Re-scale if widget was resized since last set_image()
            if (w, h) != self._cached_size and self._image is not None:
                self._scaled = self._image.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self._x_off = (w - self._scaled.width()) // 2
                self._y_off = (h - self._scaled.height()) // 2
                self._cached_size = (w, h)

            x_off = self._x_off
            y_off = self._y_off
            p.drawImage(x_off, y_off, self._scaled)

            # Corner brackets (no antialiasing needed for straight lines)
            self._draw_corner_brackets(p, x_off, y_off, self._scaled.width(), self._scaled.height())

            # Hand landmarks (no antialiasing for skeleton lines)
            if self._landmarks and self._landmarks.points:
                self._draw_landmarks(p, x_off, y_off, self._scaled.width(), self._scaled.height())
        else:
            # No signal fallback
            p.setPen(QColor(TEXT_DIM))
            font = QFont("Consolas", 14)
            p.setFont(font)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "NO SIGNAL")

        # Enable antialiasing only for badges/pills (rounded rects)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # FPS badge (top-left)
        if self._fps > 0:
            self._draw_badge(p, 12, 12, f"FPS {self._fps:.0f}", Qt.AlignmentFlag.AlignLeft)

        # Handedness badge (top-right)
        if self._handedness:
            self._draw_badge(
                p, w - 12, 12, self._handedness, Qt.AlignmentFlag.AlignRight
            )

        # Active gesture pill (bottom-center)
        if self._active_gesture and self._active_gesture != "No hand":
            self._draw_gesture_pill(p, w, h)

        p.end()

    def _draw_corner_brackets(
        self, p: QPainter, x: int, y: int, fw: int, fh: int
    ) -> None:
        """Draw L-shaped corner brackets around the camera frame."""
        bracket_len = 30
        inset = 8
        color = QColor(ACCENT)
        color.setAlpha(153)  # 60%
        pen = QPen(color, 2)
        p.setPen(pen)

        corners = [
            # top-left
            (x + inset, y + inset, x + inset + bracket_len, y + inset,
             x + inset, y + inset, x + inset, y + inset + bracket_len),
            # top-right
            (x + fw - inset - bracket_len, y + inset, x + fw - inset, y + inset,
             x + fw - inset, y + inset, x + fw - inset, y + inset + bracket_len),
            # bottom-left
            (x + inset, y + fh - inset, x + inset + bracket_len, y + fh - inset,
             x + inset, y + fh - inset - bracket_len, x + inset, y + fh - inset),
            # bottom-right
            (x + fw - inset - bracket_len, y + fh - inset, x + fw - inset, y + fh - inset,
             x + fw - inset, y + fh - inset - bracket_len, x + fw - inset, y + fh - inset),
        ]
        for x1, y1, x2, y2, x3, y3, x4, y4 in corners:
            p.drawLine(x1, y1, x2, y2)
            p.drawLine(x3, y3, x4, y4)

    def _draw_landmarks(
        self, p: QPainter, x_off: int, y_off: int, fw: int, fh: int
    ) -> None:
        """Draw hand landmark dots, skeleton lines, and palm crosshair."""
        points = self._landmarks.points

        # Skeleton lines
        line_color = QColor(ACCENT)
        line_color.setAlpha(180)  # 70%
        p.setPen(QPen(line_color, 3))
        for i, j in HAND_CONNECTIONS:
            if i < len(points) and j < len(points):
                px1 = x_off + int(points[i][0] * fw)
                py1 = y_off + int(points[i][1] * fh)
                px2 = x_off + int(points[j][0] * fw)
                py2 = y_off + int(points[j][1] * fh)
                p.drawLine(px1, py1, px2, py2)

        # Landmark dots
       # dot_color = QColor(ACCENT_LIGHT) # OLD COLOR
        dot_color = QColor("#ef4444")
        dot_color.setAlpha(230)  # 90%
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dot_color))
        for px, py, _pz in points:
            sx = x_off + int(px * fw)
            sy = y_off + int(py * fh)
            p.drawEllipse(sx - 4, sy - 4, 8, 8)

        # Palm crosshair (landmark 9 = middle finger MCP, center of palm)
        if len(points) > 9:
            cx = x_off + int(points[9][0] * fw)
            cy = y_off + int(points[9][1] * fh)
            cross_color = QColor("#22c55e")
            cross_color.setAlpha(180)
            p.setPen(QPen(cross_color, 2.5))
            cross_size = 14
            p.drawLine(cx - cross_size, cy, cx + cross_size, cy)
            p.drawLine(cx, cy - cross_size, cx, cy + cross_size)

    def _draw_badge(
        self, p: QPainter, x: int, y: int, text: str, align: Qt.AlignmentFlag
    ) -> None:
        """Draw a small pill badge with dark background."""
        font = QFont("Consolas", 9)
        p.setFont(font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 16
        th = metrics.height() + 8

        if align == Qt.AlignmentFlag.AlignRight:
            rx = x - tw
        else:
            rx = x

        bg = QColor(BACKGROUND)
        bg.setAlpha(200)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(rx, y, tw, th), 4, 4)

        p.setPen(QColor(TEXT_MUTED))
        p.drawText(QRectF(rx, y, tw, th), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_gesture_pill(self, p: QPainter, w: int, h: int) -> None:
        """Draw the active gesture pill at bottom-center."""
        text = f"{self._active_gesture}  {self._active_confidence:.0%}"
        font = QFont("Consolas", 11, QFont.Weight.Bold)
        p.setFont(font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 28
        th = metrics.height() + 14

        rx = (w - tw) // 2
        ry = h - th - 16

        bg = QColor(SURFACE)
        bg.setAlpha(217)  # 85%
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(rx, ry, tw, th), th // 2, th // 2)

        p.setPen(QColor(TEXT_PRIMARY))
        p.drawText(QRectF(rx, ry, tw, th), Qt.AlignmentFlag.AlignCenter, text)


class ConfidenceBarsWidget(QWidget):
    """Custom widget that draws horizontal confidence bars for all gestures."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scores: dict[str, float] = {}
        self._top_gesture: str = ""
        self.setMinimumHeight(len(_BAR_LABELS) * 32 + 10)

    def set_scores(self, scores: dict[str, float], top_gesture_label: str) -> None:
        """Update scores and trigger repaint."""
        self._scores = scores
        self._top_gesture = top_gesture_label
        self.update()

    def paintEvent(self, event) -> None:
        """Draw confidence bars."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()

        bar_height = 6
        row_height = 32
        label_font = QFont("Consolas", 9)
        pct_font = QFont("Consolas", 9)
        left_margin = 4
        right_margin = 45
        bar_left = left_margin
        bar_right = w - right_margin

        for idx, (key, display_name) in enumerate(_BAR_LABELS):
            y_base = idx * row_height + 8
            value = self._scores.get(key, 0.0)
            is_winner = key == self._top_gesture and value > 0

            # Left accent border for winner
            if is_winner:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(ACCENT)))
                p.drawRoundedRect(QRectF(0, y_base - 4, 2, row_height - 2), 1, 1)

            # Label
            p.setFont(label_font)
            p.setPen(QColor(TEXT_SECONDARY if is_winner else TEXT_DIM))
            p.drawText(
                QRectF(bar_left, y_base - 2, bar_right - bar_left, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                display_name,
            )

            # Track background
            track_y = y_base + 16
            track_w = bar_right - bar_left
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(SURFACE)))
            p.drawRoundedRect(QRectF(bar_left, track_y, track_w, bar_height), 3, 3)

            # Fill bar
            fill_w = track_w * value
            if fill_w > 0:
                if is_winner:
                    # Glow effect: draw slightly larger, low-alpha version behind
                    glow_color = QColor(ACCENT)
                    glow_color.setAlpha(50)
                    p.setBrush(QBrush(glow_color))
                    p.drawRoundedRect(
                        QRectF(bar_left - 1, track_y - 1, fill_w + 2, bar_height + 2), 4, 4
                    )
                    p.setBrush(QBrush(QColor(ACCENT)))
                else:
                    dim_color = QColor(TEXT_DIM)
                    dim_color.setAlpha(128)
                    p.setBrush(QBrush(dim_color))
                p.drawRoundedRect(QRectF(bar_left, track_y, fill_w, bar_height), 3, 3)

            # Percentage text
            p.setFont(pct_font)
            p.setPen(QColor(TEXT_SECONDARY if is_winner else TEXT_DIM))
            pct_text = f"{value:.0%}" if value > 0 else "--"
            p.drawText(
                QRectF(bar_right + 4, track_y - 6, right_margin - 4, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                pct_text,
            )

        p.end()


class SidePanel(QWidget):
    """Right-side HUD panel showing confidence bars, state, and telemetry."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f"""
            background-color: {BACKGROUND};
            border-left: 1px solid rgba(255,255,255,0.06);
        """)

        self._state = GestureState.IDLE
        self._fps: float = 0.0
        self._handedness: str = "--"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # Header
        self._header = _make_section_header("GESTUREMUTE HUD")
        layout.addWidget(self._header)
        layout.addSpacing(16)

        # Confidence section
        self._conf_header = _make_section_header("CONFIDENCE")
        layout.addWidget(self._conf_header)
        layout.addSpacing(6)

        self._bars = ConfidenceBarsWidget()
        layout.addWidget(self._bars)
        layout.addSpacing(16)

        # State section
        self._state_header = _make_section_header("STATE")
        layout.addWidget(self._state_header)
        layout.addSpacing(6)

        self._state_widget = StatePillWidget()
        layout.addWidget(self._state_widget)
        layout.addSpacing(16)

        # Telemetry section
        self._telemetry_header = _make_section_header("TELEMETRY")
        layout.addWidget(self._telemetry_header)
        layout.addSpacing(6)

        self._telemetry_widget = TelemetryWidget()
        layout.addWidget(self._telemetry_widget)

        layout.addStretch()

    def update_scores(self, scores: GestureScores) -> None:
        """Update the confidence bars."""
        top_label = scores.top_gesture.to_label() if scores.top_gesture else "None"
        self._bars.set_scores(scores.scores, top_label)

    def update_state(self, state: GestureState) -> None:
        """Update the state pill."""
        self._state = state
        self._state_widget.set_state(state)

    def update_telemetry(self, fps: float, handedness: str) -> None:
        """Update the telemetry display."""
        self._telemetry_widget.set_values(fps, handedness)


class StatePillWidget(QWidget):
    """Draws a colored rounded rect pill showing the current GestureState."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = GestureState.IDLE
        self.setFixedHeight(32)

    def set_state(self, state: GestureState) -> None:
        """Update the displayed state."""
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the state pill."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_hex = _STATE_COLORS.get(self._state, TEXT_DIM)
        color = QColor(color_hex)
        text = self._state.name.replace("_", " ")
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        p.setFont(font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 24
        th = 26

        # Pill background (dimmed)
        bg = QColor(color_hex)
        bg.setAlpha(30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(0, 2, tw, th), th // 2, th // 2)

        # Pill border
        border = QColor(color_hex)
        border.setAlpha(120)
        p.setPen(QPen(border, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 2, tw, th), th // 2, th // 2)

        # Text
        p.setPen(color)
        p.drawText(QRectF(0, 2, tw, th), Qt.AlignmentFlag.AlignCenter, text)

        p.end()


class TelemetryWidget(QWidget):
    """Displays FPS and handedness key-value pairs in monospace."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fps: float = 0.0
        self._handedness: str = "--"
        self.setFixedHeight(50)

    def set_values(self, fps: float, handedness: str) -> None:
        """Update telemetry values."""
        self._fps = fps
        self._handedness = handedness
        self.update()

    def paintEvent(self, event) -> None:
        """Draw telemetry key-value pairs."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Consolas", 10)
        p.setFont(font)

        # FPS
        p.setPen(QColor(TEXT_DIM))
        p.drawText(4, 16, "FPS")
        p.setPen(QColor(TEXT_SECONDARY))
        p.drawText(60, 16, f"{self._fps:.0f}")

        # Handedness
        p.setPen(QColor(TEXT_DIM))
        p.drawText(4, 38, "Hand")
        p.setPen(QColor(TEXT_SECONDARY))
        p.drawText(60, 38, self._handedness)

        p.end()


def _make_section_header(text: str) -> QWidget:
    """Create a section header label widget."""
    from PyQt6.QtWidgets import QLabel
    label = QLabel(text)
    label.setStyleSheet(f"""
        color: {TEXT_DIM};
        font-family: Consolas;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 2px;
        background: transparent;
        border: none;
    """)
    label.setFixedHeight(16)
    return label


class PreviewWindow(QWidget):
    """HUD dashboard window showing live camera feed with gesture monitoring.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GestureMute HUD")
        self.setMinimumSize(900, 520)
        self.setStyleSheet(f"background-color: {BACKGROUND};")

        self._gesture_text = "No hand"
        self._confidence = 0.0
        self._timestamps: collections.deque[float] = collections.deque(maxlen=30)
        self._current_fps: float = 0.0
        self._current_handedness: str = ""
        self._paused: bool = False

        # Layout: camera canvas + side panel
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._canvas = CameraCanvas()
        self._side_panel = SidePanel()

        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._side_panel)

    def clear_frame(self) -> None:
        """Clear the camera feed and reset all telemetry to show NO SIGNAL."""
        self._paused = True
        self._canvas.clear_frame()
        self._gesture_text = "No hand"
        self._confidence = 0.0
        self._current_fps = 0.0
        self._current_handedness = ""
        self._side_panel.update_telemetry(0.0, "")

    def resume(self) -> None:
        """Re-enable frame updates after a pause."""
        self._paused = False

    @pyqtSlot(np.ndarray, int)
    def update_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Display a BGR frame from the camera and update FPS.

        Args:
            frame: BGR image from OpenCV.
            timestamp_ms: Frame timestamp.
        """
        if self._paused:
            return

        # FPS calculation
        now = time.monotonic()
        self._timestamps.append(now)
        if len(self._timestamps) >= 2:
            elapsed = self._timestamps[-1] - self._timestamps[0]
            if elapsed > 0:
                self._current_fps = (len(self._timestamps) - 1) / elapsed

        # Convert frame to QImage
        rgb = frame[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

        self._canvas.set_fps(self._current_fps)
        self._canvas.set_image(image)
        self._side_panel.update_telemetry(self._current_fps, self._current_handedness)

    @pyqtSlot(object)
    def update_scores(self, scores: GestureScores) -> None:
        """Update the side panel confidence bars.

        Args:
            scores: All gesture confidence scores.
        """
        self._side_panel.update_scores(scores)

        # Also update the canvas active gesture pill
        if scores.top_gesture != Gesture.NONE and scores.top_confidence > 0:
            name = scores.top_gesture.to_label().replace("_", " ")
            self._canvas.set_active_gesture(name, scores.top_confidence)
            self._gesture_text = name
            self._confidence = scores.top_confidence
        else:
            self._canvas.set_active_gesture("", 0.0)
            self._gesture_text = "No hand"
            self._confidence = 0.0

    @pyqtSlot(object)
    def update_landmarks(self, landmarks: HandLandmarks | None) -> None:
        """Update the canvas hand landmark overlay.

        Args:
            landmarks: Hand landmark data or None if no hand.
        """
        self._canvas.set_landmarks(landmarks)
        if landmarks and landmarks.handedness != "Unknown":
            self._current_handedness = landmarks.handedness
            self._canvas.set_handedness(landmarks.handedness)
        elif landmarks is None:
            self._current_handedness = ""
            self._canvas.set_handedness("")

    @pyqtSlot(object, object)
    def update_state(self, old_state, new_state) -> None:
        """Update the state machine pill.

        Args:
            old_state: Previous GestureState.
            new_state: New GestureState.
        """
        if isinstance(new_state, GestureState):
            self._side_panel.update_state(new_state)

    @pyqtSlot(object, float)
    def update_gesture(self, gesture: Gesture, confidence: float) -> None:
        """Backward-compatible gesture update.

        Args:
            gesture: Detected gesture.
            confidence: Detection confidence (0-1).
        """
        self._gesture_text = gesture.name
        self._confidence = confidence

    @pyqtSlot()
    def update_no_hand(self) -> None:
        """Backward-compatible no-hand update."""
        self._gesture_text = "No hand"
        self._confidence = 0.0
