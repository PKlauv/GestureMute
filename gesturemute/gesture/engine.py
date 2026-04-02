"""MediaPipe gesture recognizer wrapper."""

import logging
import queue
import threading
import time

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
from gesturemute.events.signal import Signal
from gesturemute.gesture.gestures import Gesture, GestureScores, HandLandmarks

logger = logging.getLogger(__name__)


def _is_palm_facing_camera(
    landmarks: list, handedness: str
) -> bool:
    """Check if the palm faces the camera using cross-product of hand surface vectors.

    Uses wrist (0), index MCP (5), and pinky MCP (17) to form a triangle
    on the palm surface. The cross-product z-component sign indicates
    which side faces the camera, flipped by handedness.
    """
    wrist = landmarks[0]
    index_mcp = landmarks[5]
    pinky_mcp = landmarks[17]

    # Vectors on the palm plane
    v1 = (index_mcp.x - wrist.x, index_mcp.y - wrist.y)
    v2 = (pinky_mcp.x - wrist.x, pinky_mcp.y - wrist.y)

    # Cross product z-component (2D cross product)
    cross_z = v1[0] * v2[1] - v1[1] * v2[0]

    # For a "Right" hand with palm facing camera, cross_z is typically negative
    # For a "Left" hand with palm facing camera, cross_z is typically positive
    if handedness == "Right":
        return cross_z < 0
    else:
        return cross_z > 0


class GestureEngine:
    """Wraps MediaPipe GestureRecognizer in LIVE_STREAM mode.

    Results are pushed to a thread-safe queue by the async callback and
    consumed via drain_results() on the main thread.

    Args:
        config: Application configuration.
    """

    _MAX_QUEUE_SIZE = 50

    def __init__(self, config: Config) -> None:
        self._config = config
        self._last_ts: int = -1
        self._results: queue.Queue[tuple[Gesture, float]] = queue.Queue(
            maxsize=self._MAX_QUEUE_SIZE
        )
        self._rich_results: queue.Queue[tuple[GestureScores, HandLandmarks | None]] = queue.Queue(
            maxsize=self._MAX_QUEUE_SIZE
        )

        options = GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=config.model_path),
            running_mode=RunningMode.LIVE_STREAM,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=self._on_result,
        )
        self._recognizer = GestureRecognizer.create_from_options(options)
        logger.info("GestureEngine initialized with model: %s", config.model_path)

    def _hands_are_close(self, landmarks1: list, landmarks2: list) -> bool:
        """Check if two hands are close together using wrist landmark distance.

        Args:
            landmarks1: Hand landmarks for the first hand.
            landmarks2: Hand landmarks for the second hand.

        Returns:
            True if wrist-to-wrist distance is below the configured threshold.
        """
        wrist1 = landmarks1[0]
        wrist2 = landmarks2[0]
        dx = wrist1.x - wrist2.x
        dy = wrist1.y - wrist2.y
        distance = (dx * dx + dy * dy) ** 0.5
        return distance < self._config.two_fists_max_distance

    def _build_all_landmarks(self, result: GestureRecognizerResult) -> list[HandLandmarks] | None:
        """Build HandLandmarks for every detected hand."""
        if not result.hand_landmarks:
            return None
        all_landmarks = []
        for hi, hand_lms in enumerate(result.hand_landmarks):
            if hand_lms:
                points = [(lm.x, lm.y, lm.z) for lm in hand_lms]
                handedness_str = "Unknown"
                if (result.handedness
                        and hi < len(result.handedness)
                        and result.handedness[hi]):
                    handedness_str = result.handedness[hi][0].category_name
                all_landmarks.append(HandLandmarks(points=points, handedness=handedness_str))
        return all_landmarks if all_landmarks else None

    def _on_result(
        self,
        result: GestureRecognizerResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        """MediaPipe async callback — pushes results to thread-safe queue."""
        try:
            # Guard: no gestures at all → emit NONE but still show tracked hands
            if not result.gestures or not result.gestures[0]:
                self._put_result((Gesture.NONE, 0.0))
                self._put_rich_result((
                    GestureScores(scores={}, top_gesture=Gesture.NONE, top_confidence=0.0),
                    self._build_all_landmarks(result),             # ← draw hands anyway
                ))
                return

            # Log ALL recognized gestures before filtering (debug diagnostics)
            for hand_idx, hand_gestures in enumerate(result.gestures):
                labels = [(g.category_name, f"{g.score:.2%}") for g in hand_gestures]
                logger.debug("Hand %d raw gestures: %s", hand_idx, labels)

            # Check for TWO_FISTS_CLOSE: 2 hands, both Closed_Fist, close together
            if (
                len(result.gestures) >= 2
                and result.gestures[0]
                and result.gestures[1]
                and result.hand_landmarks
                and len(result.hand_landmarks) >= 2
            ):
                fist1 = result.gestures[0][0]
                fist2 = result.gestures[1][0]
                if (
                    fist1.category_name == "Closed_Fist"
                    and fist2.category_name == "Closed_Fist"
                    and self._hands_are_close(
                        result.hand_landmarks[0], result.hand_landmarks[1]
                    )
                ):
                    composite_conf = min(fist1.score, fist2.score)
                    self._put_result((Gesture.TWO_FISTS_CLOSE, composite_conf))
                    scores = {g.category_name: g.score for g in result.gestures[0]}
                    gesture_scores = GestureScores(
                        scores=scores,
                        top_gesture=Gesture.TWO_FISTS_CLOSE,
                        top_confidence=composite_conf,
                    )
                    # Build landmarks for ALL detected hands
                    self._put_rich_result((gesture_scores, self._build_all_landmarks(result)))
                    return

            # Single-hand fallback: use first hand
            # Re-check in case gestures[0] became empty
            if not result.gestures[0]:
                self._put_result((Gesture.NONE, 0.0))
                self._put_rich_result((
                    GestureScores(scores={}, top_gesture=Gesture.NONE, top_confidence=0.0),
                    self._build_all_landmarks(result),             # ← draw hands anyway
                ))
                return

            top: Category = result.gestures[0][0]
            gesture = Gesture.from_label(top.category_name)

            # Reject Open_Palm if palm faces away from camera
            if gesture == Gesture.OPEN_PALM and result.hand_landmarks and result.hand_landmarks[0]:
                lms = result.hand_landmarks[0]
                handedness = "Unknown"
                if result.handedness and result.handedness[0]:
                    handedness = result.handedness[0][0].category_name
                if not _is_palm_facing_camera(lms, handedness):
                    gesture = Gesture.NONE

            self._put_result((gesture, top.score))

            # Build rich results for HUD — ALL hands
            scores = {g.category_name: g.score for g in result.gestures[0]}
            gesture_scores = GestureScores(
                scores=scores, top_gesture=gesture, top_confidence=top.score,
            )
            self._put_rich_result((gesture_scores, self._build_all_landmarks(result)))
        except Exception:
            logger.exception("Error processing gesture result")

    def _put_result(self, item: tuple[Gesture, float]) -> None:
        """Add a result to the queue, dropping oldest if full."""
        if self._results.full():
            try:
                self._results.get_nowait()
            except queue.Empty:
                pass
        self._results.put_nowait(item)

    def _put_rich_result(self, item: tuple[GestureScores, HandLandmarks | None]) -> None:
        """Add a rich result to the queue, dropping oldest if full."""
        if self._rich_results.full():
            try:
                self._rich_results.get_nowait()
            except queue.Empty:
                pass
        self._rich_results.put_nowait(item)

    def process_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Submit a frame for async gesture recognition.

        Args:
            frame: BGR image from OpenCV.
            timestamp_ms: Monotonic timestamp in milliseconds.
        """
        if timestamp_ms <= self._last_ts:
            timestamp_ms = self._last_ts + 1
        self._last_ts = timestamp_ms

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

    def drain_rich_results(self) -> list[tuple[GestureScores, HandLandmarks | None]]:
        """Drain all queued rich results. Call from the worker thread.

        Returns:
            List of (GestureScores, HandLandmarks | None) tuples.
        """
        results = []
        while not self._rich_results.empty():
            try:
                results.append(self._rich_results.get_nowait())
            except queue.Empty:
                break
        return results

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._recognizer.close()
        logger.info("GestureEngine closed")


class GestureWorker:
    """Thread wrapper around GestureEngine with a locked frame buffer.

    Receives frames via set_frame() from the camera thread and processes
    them on its own thread. Emits signals back to listeners.

    Signals (Signal instances):
        gesture_detected: Emitted with (gesture, confidence) for recognized gestures.
        no_hand: Emitted when no hand is detected in a frame.
        all_scores: Emitted with GestureScores for debug/preview.
        landmarks: Emitted with HandLandmarks for debug/preview.
        engine_ready: Emitted when MediaPipe model is loaded.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._engine: GestureEngine | None = None
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._frame_ts: int = 0
        self._running = False
        self._thread: threading.Thread | None = None

        # Signals (drop-in replacements for pyqtSignal)
        self.gesture_detected = Signal()
        self.no_hand = Signal()
        self.all_scores = Signal()
        self.landmarks = Signal()
        self.engine_ready = Signal()

    def set_frame(self, frame: np.ndarray, timestamp_ms: int) -> None:
        """Thread-safe frame setter — called from the camera thread.

        Args:
            frame: BGR image from OpenCV.
            timestamp_ms: Monotonic timestamp in milliseconds.
        """
        with self._lock:
            self._frame = frame.copy()
            self._frame_ts = timestamp_ms

    def start(self) -> None:
        """Start the processing thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="GestureWorker")
        self._thread.start()

    def _run(self) -> None:
        """Processing loop — creates engine, processes frames, emits signals."""
        t0 = time.perf_counter()
        self._engine = GestureEngine(self._config)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("GestureEngine created in %.0fms", elapsed)
        self.engine_ready.emit()

        while self._running:
            with self._lock:
                frame = self._frame
                ts = self._frame_ts
                self._frame = None

            if frame is None:
                time.sleep(0.005)
                continue

            self._engine.process_frame(frame, ts)
            del frame

            for gesture, confidence in self._engine.drain_results():
                if gesture == Gesture.NONE:
                    self.no_hand.emit()
                else:
                    self.gesture_detected.emit(gesture, confidence)

            for scores, lm in self._engine.drain_rich_results():
                self.all_scores.emit(scores)
                self.landmarks.emit(lm)

        if self._engine is not None:
            self._engine.close()
            self._engine = None

    def stop(self) -> None:
        """Signal the processing loop to stop and wait for thread exit."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
