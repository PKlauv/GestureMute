"""OpenCV webcam capture module."""

import logging
import sys
import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from gesturemute.config import Config

logger = logging.getLogger(__name__)


class Camera:
    """Manages webcam capture via OpenCV.

    Args:
        config: Application configuration.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._cap: cv2.VideoCapture | None = None
        self._frame_count = 0

    def _resolve_backend(self) -> int:
        """Map the config camera_backend string to an OpenCV backend constant."""
        backend_map = {
            "dshow": cv2.CAP_DSHOW,
            "msmf": cv2.CAP_MSMF,
            "any": cv2.CAP_ANY,
        }
        backend_str = self._config.camera_backend.lower()
        if backend_str == "auto":
            return cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        return backend_map.get(backend_str, cv2.CAP_ANY)

    def open(self) -> None:
        """Open the webcam device.

        Raises:
            RuntimeError: If the camera cannot be opened.
        """
        backend = self._resolve_backend()
        self._cap = cv2.VideoCapture(self._config.camera_index, backend)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera at index {self._config.camera_index}. "
                "Check that a webcam is connected."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # Discard initial warmup frames to avoid black/corrupt first frames
        for _ in range(3):
            self._cap.read()
        logger.info(
            "Camera opened at index %d (640x480, backend=%s)",
            self._config.camera_index, self._config.camera_backend,
        )

    def read_frame(self) -> tuple[bool, np.ndarray | None, int]:
        """Read a single frame from the webcam.

        Returns:
            Tuple of (success, frame, timestamp_ms). Frame is None on failure.
        """
        if self._cap is None:
            return False, None, 0

        success, frame = self._cap.read()
        timestamp_ms = time.monotonic_ns() // 1_000_000
        self._frame_count += 1

        if not success:
            logger.warning("Failed to read frame from camera")
            return False, None, timestamp_ms

        return True, frame, timestamp_ms

    def should_process(self) -> bool:
        """Return True if the current frame should be processed.

        Implements frame skipping to reduce CPU usage.
        """
        return self._frame_count % self._config.frame_skip == 0

    def close(self) -> None:
        """Release the webcam device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera closed")


class CameraWorker(QThread):
    """QThread wrapper around Camera for non-blocking frame capture.

    Signals:
        frame_ready: Emitted with (frame, timestamp_ms) when a processable frame is captured.
        error: Emitted with an error message string on camera failure.
        camera_lost: Emitted when camera disconnects after repeated read failures.
        camera_restored: Emitted when camera reconnects after being lost.
    """

    _MAX_CONSECUTIVE_FAILURES = 30
    _RECONNECT_DELAYS = [1, 2, 4, 8, 16]  # seconds, capped at last value

    frame_ready = pyqtSignal(np.ndarray, int)
    error = pyqtSignal(str)
    camera_lost = pyqtSignal()
    camera_restored = pyqtSignal()

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._camera = Camera(config)
        self._running = False

    def run(self) -> None:
        """Capture loop — opens camera, emits frames, reconnects on failure."""
        try:
            self._camera.open()
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        self._running = True
        consecutive_failures = 0

        while self._running:
            success, frame, timestamp_ms = self._camera.read_frame()
            if not success:
                consecutive_failures += 1
                if consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "Camera lost after %d consecutive failures, attempting reconnect",
                        consecutive_failures,
                    )
                    self.camera_lost.emit()
                    self._reconnect()
                    consecutive_failures = 0
                else:
                    self.msleep(10)
                continue

            consecutive_failures = 0

            if self._camera.should_process():
                self.frame_ready.emit(frame, timestamp_ms)

            del frame
            self.msleep(5)

        self._camera.close()

    def _reconnect(self) -> None:
        """Close and reopen the camera with exponential backoff."""
        self._camera.close()
        for attempt in range(len(self._RECONNECT_DELAYS) + 1):
            if not self._running:
                return
            delay = self._RECONNECT_DELAYS[min(attempt, len(self._RECONNECT_DELAYS) - 1)]
            logger.info("Reconnect attempt %d, waiting %ds...", attempt + 1, delay)
            # Sleep in small increments so we can respond to stop()
            for _ in range(delay * 20):
                if not self._running:
                    return
                self.msleep(50)
            try:
                self._camera.open()
                logger.info("Camera reconnected on attempt %d", attempt + 1)
                self.camera_restored.emit()
                return
            except RuntimeError:
                logger.warning("Reconnect attempt %d failed", attempt + 1)
        # All attempts exhausted
        self.error.emit("Camera reconnection failed after all retry attempts")

    def stop(self) -> None:
        """Signal the capture loop to stop and wait for thread exit."""
        self._running = False
        self.wait()
