"""OpenCV webcam capture module."""

import logging
import time

import cv2
import numpy as np

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

    def open(self) -> None:
        """Open the webcam device.

        Raises:
            RuntimeError: If the camera cannot be opened.
        """
        self._cap = cv2.VideoCapture(self._config.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera at index {self._config.camera_index}. "
                "Check that a webcam is connected."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        logger.info("Camera opened at index %d (640x480)", self._config.camera_index)

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
