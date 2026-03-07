"""Live camera preview window with gesture/confidence overlay for debugging."""

import numpy as np
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gesturemute.gesture.gestures import Gesture


class PreviewWindow(QWidget):
    """Debug window showing live camera feed with gesture annotations.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GestureMute Preview")
        self.setMinimumSize(640, 480)

        self._gesture_text = "No hand"
        self._confidence = 0.0

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: black;")

        self._info_label = QLabel("Waiting for frames...")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: white; "
            "background-color: rgba(0, 0, 0, 180); padding: 8px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._image_label, stretch=1)
        layout.addWidget(self._info_label)

    @pyqtSlot(np.ndarray, int)
    def update_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Display a BGR frame from the camera.

        Args:
            frame: BGR image from OpenCV.
            timestamp_ms: Frame timestamp (unused, kept for signal compatibility).
        """
        rgb = frame[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self._image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(pixmap)

    @pyqtSlot(object, float)
    def update_gesture(self, gesture: Gesture, confidence: float) -> None:
        """Update the gesture overlay text.

        Args:
            gesture: Detected gesture.
            confidence: Detection confidence (0-1).
        """
        self._gesture_text = gesture.name
        self._confidence = confidence
        self._info_label.setText(f"{self._gesture_text}  —  {self._confidence:.0%}")
        self._info_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #10B981; "
            "background-color: rgba(0, 0, 0, 180); padding: 8px;"
        )

    @pyqtSlot()
    def update_no_hand(self) -> None:
        """Update overlay when no hand is detected."""
        self._gesture_text = "No hand"
        self._confidence = 0.0
        self._info_label.setText("No hand detected")
        self._info_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #9CA3AF; "
            "background-color: rgba(0, 0, 0, 180); padding: 8px;"
        )
