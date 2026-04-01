"""OpenCV webcam capture module."""

import logging
import sys
import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from gesturemute.config import Config

logger = logging.getLogger(__name__)


class AdaptiveFrameSkip:
    """Windowed-average auto-adjustment of frame skip value.

    Monitors frame *processing* times (the cost of emitting/handling a frame,
    not the wall-clock interval between camera reads) and adjusts skip value
    to maintain performance within a target range (20-40ms dead zone).

    Args:
        initial_skip: Starting frame skip value, clamped to [1, 6].
    """

    _MIN_SKIP = 1
    _MAX_SKIP = 6
    _ADJUST_INTERVAL = 30
    _HIGH_THRESHOLD = 40.0  # ms
    _LOW_THRESHOLD = 20.0   # ms

    def __init__(self, initial_skip: int = 2) -> None:
        self._skip = max(self._MIN_SKIP, min(self._MAX_SKIP, initial_skip))
        self._samples: list[float] = []

    @property
    def current_skip(self) -> int:
        """Return the current frame skip value."""
        return self._skip

    def record_frame_time(self, ms: float) -> None:
        """Append a frame time sample to the buffer.

        Args:
            ms: Frame processing time in milliseconds.
        """
        self._samples.append(ms)

    def maybe_adjust(self) -> int:
        """Check if enough samples collected and adjust skip value.

        Every 30 samples, computes the EMA of frame times and adjusts:
        - > 40ms: increase skip by 1 (max 6)
        - < 20ms: decrease skip by 1 (min 1)
        - 20-40ms: no change (hysteresis dead zone)

        Returns:
            Current skip value after any adjustment.
        """
        if len(self._samples) < self._ADJUST_INTERVAL:
            return self._skip

        avg = sum(self._samples) / len(self._samples)
        self._samples.clear()

        if avg > self._HIGH_THRESHOLD:
            self._skip = min(self._MAX_SKIP, self._skip + 1)
        elif avg < self._LOW_THRESHOLD:
            self._skip = max(self._MIN_SKIP, self._skip - 1)

        return self._skip


class Camera:
    """Manages webcam capture via OpenCV.

    Args:
        config: Application configuration.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._cap: cv2.VideoCapture | None = None
        self._frame_count = 0
        self._adaptive: AdaptiveFrameSkip | None = (
            AdaptiveFrameSkip(initial_skip=config.frame_skip)
            if config.adaptive_frame_skip else None
        )

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
        t0 = time.perf_counter()
        backend = self._resolve_backend()
        self._cap = cv2.VideoCapture(self._config.camera_index, backend)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera at index {self._config.camera_index}. "
                "Check that a webcam is connected."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        t_open = time.perf_counter()
        # Discard initial warmup frames to avoid black/corrupt first frames
        for _ in range(3):
            self._cap.read()
        t_warmup = time.perf_counter()
        logger.info(
            "Camera opened at index %d (640x480, backend=%s) — open=%.0fms, warmup=%.0fms, total=%.0fms",
            self._config.camera_index, self._config.camera_backend,
            (t_open - t0) * 1000, (t_warmup - t_open) * 1000, (t_warmup - t0) * 1000,
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
            logger.debug("Failed to read frame from camera")
            return False, None, timestamp_ms

        frame = cv2.flip(frame, 1)  # Horizontal flip (mirror)

        return True, frame, timestamp_ms

    def should_process(self) -> bool:
        """Return True if the current frame should be processed.

        Implements frame skipping to reduce CPU usage. Uses adaptive skip
        value when adaptive mode is active, otherwise uses static config.
        """
        skip = self._adaptive.current_skip if self._adaptive else self._config.frame_skip
        return self._frame_count % skip == 0

    def record_frame_time(self, ms: float) -> None:
        """Record a frame processing time sample for adaptive skip adjustment.

        Args:
            ms: Time spent processing (emitting) the frame, in milliseconds.
                 This should NOT include camera read blocking time or sleep.
        """
        if self._adaptive:
            self._adaptive.record_frame_time(ms)
            self._adaptive.maybe_adjust()

    def update_config(self, config: "Config") -> None:
        """Update configuration (e.g. frame_skip, adaptive mode) at runtime."""
        self._config = config
        if config.adaptive_frame_skip:
            if self._adaptive is None:
                self._adaptive = AdaptiveFrameSkip(initial_skip=config.frame_skip)
        else:
            self._adaptive = None

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
    camera_ready = pyqtSignal()

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._camera = Camera(config)
        self._running = False

    def update_config(self, config: Config) -> None:
        """Forward config update to the inner Camera."""
        self._config = config
        self._camera.update_config(config)

    def run(self) -> None:
        """Capture loop — opens camera, emits frames, reconnects on failure."""
        try:
            self._camera.open()
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        self.camera_ready.emit()
        self._running = True
        consecutive_failures = 0

        while self._running:
            success, frame, timestamp_ms = self._camera.read_frame()
            if not success:
                consecutive_failures += 1
                if consecutive_failures == 1:
                    logger.warning(
                        "Camera frame read failed, monitoring... "
                        "(reconnect after %d failures)",
                        self._MAX_CONSECUTIVE_FAILURES,
                    )
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
                t0 = time.monotonic_ns()
                self.frame_ready.emit(frame, timestamp_ms)
                process_ms = (time.monotonic_ns() - t0) / 1_000_000
                self._camera.record_frame_time(process_ms)

            del frame
            self.msleep(5)

        self._camera.close()

    def _sleep_interruptible(self, seconds: int) -> bool:
        """Sleep in small increments, returning False if stop() was called."""
        for _ in range(seconds * 20):
            if not self._running:
                return False
            self.msleep(50)
        return True

    def _reconnect(self) -> None:
        """Close and reopen the camera with exponential backoff.

        Tries the current index first (3 attempts), then scans all
        non-iPhone cameras on macOS as fallbacks.
        """
        self._camera.close()

        # Phase 1: retry current index with backoff
        for attempt in range(3):
            if not self._running:
                return
            delay = self._RECONNECT_DELAYS[min(attempt, len(self._RECONNECT_DELAYS) - 1)]
            logger.info("Reconnect attempt %d at index %d, waiting %ds...",
                        attempt + 1, self._config.camera_index, delay)
            if not self._sleep_interruptible(delay):
                return
            try:
                self._camera.open()
                logger.info("Camera reconnected on attempt %d", attempt + 1)
                self.camera_restored.emit()
                return
            except RuntimeError:
                logger.warning("Reconnect attempt %d failed", attempt + 1)

        # Phase 2: scan all non-iPhone cameras on macOS
        if sys.platform == "darwin":
            from gesturemute.camera.enumerate import (
                invalidate_cache,
                list_cameras_full,
            )
            invalidate_cache()  # re-query in case devices changed
            for idx, name, uid in list_cameras_full():
                if not self._running:
                    return
                if idx == self._config.camera_index:
                    continue
                logger.info("Trying alternative camera '%s' at index %d", name, idx)
                self._config.camera_index = idx
                self._config.camera_name = name
                self._config.camera_unique_id = uid
                self._camera.update_config(self._config)
                try:
                    self._camera.open()
                    logger.info("Reconnected to '%s' at index %d", name, idx)
                    self.camera_restored.emit()
                    return
                except RuntimeError:
                    logger.warning("Camera '%s' at index %d failed", name, idx)

        self.error.emit("No working camera found after scanning all devices")

    def stop(self) -> None:
        """Signal the capture loop to stop and wait for thread exit."""
        self._running = False
        self.wait()
