"""MediaPipe gesture recognizer wrapper."""

import logging
import queue

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.components.containers import Category
from mediapipe.tasks.python.vision import (
    GestureRecognizer,
    GestureRecognizerOptions,
    GestureRecognizerResult,
    RunningMode,
)

from gesturemute.config import Config
from gesturemute.gesture.gestures import Gesture

logger = logging.getLogger(__name__)


class GestureEngine:
    """Wraps MediaPipe GestureRecognizer in LIVE_STREAM mode.

    Results are pushed to a thread-safe queue by the async callback and
    consumed via drain_results() on the main thread.

    Args:
        config: Application configuration.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._results: queue.Queue[tuple[Gesture, float]] = queue.Queue()

        options = GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=config.model_path),
            running_mode=RunningMode.LIVE_STREAM,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=self._on_result,
        )
        self._recognizer = GestureRecognizer.create_from_options(options)
        logger.info("GestureEngine initialized with model: %s", config.model_path)

    def _on_result(
        self,
        result: GestureRecognizerResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        """MediaPipe async callback — pushes results to thread-safe queue."""
        if not result.gestures:
            self._results.put((Gesture.NONE, 0.0))
            return

        top: Category = result.gestures[0][0]
        gesture = Gesture.from_label(top.category_name)
        self._results.put((gesture, top.score))

    def process_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Submit a frame for async gesture recognition.

        Args:
            frame: BGR image from OpenCV.
            timestamp_ms: Monotonic timestamp in milliseconds.
        """
        rgb = frame[:, :, ::-1]  # BGR -> RGB
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        self._recognizer.recognize_async(mp_image, timestamp_ms)

    def drain_results(self) -> list[tuple[Gesture, float]]:
        """Drain all queued results. Call from the main thread.

        Returns:
            List of (Gesture, confidence) tuples.
        """
        results = []
        while not self._results.empty():
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                break
        return results

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._recognizer.close()
        logger.info("GestureEngine closed")
