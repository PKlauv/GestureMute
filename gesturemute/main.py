"""GestureMute entry point — PyQt6 system tray app with webcam gesture recognition."""

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtWidgets import QApplication

from gesturemute.camera.capture import CameraWorker
from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.engine import GestureWorker
from gesturemute.gesture.gestures import Gesture, MicState
from gesturemute.gesture.state_machine import GestureStateMachine
from gesturemute.ui.overlay import StatusOverlay
from gesturemute.ui.toast import ToastManager
from gesturemute.ui.tray import SystemTray

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
)


def _ensure_model(model_path: str) -> None:
    """Download the MediaPipe gesture recognizer model if not present.

    Args:
        model_path: Path where the model file should exist.
    """
    path = Path(model_path)
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading gesture model to {path}...")
    urllib.request.urlretrieve(MODEL_URL, path)
    print("Download complete.")


def _create_audio_controller():
    """Create the platform-appropriate audio controller."""
    if sys.platform == "win32":
        from gesturemute.audio.windows import WindowsAudioController
        return WindowsAudioController()
    elif sys.platform == "darwin":
        from gesturemute.audio.macos import MacOSAudioController
        return MacOSAudioController()
    else:
        logger.warning("No audio controller for platform %s — running in dry-run mode", sys.platform)
        return None


class AppController(QObject):
    """Wires all components together: camera, gesture, audio, and UI.

    Runs state machine and event bus callbacks on the main Qt thread.
    """

    def __init__(
        self,
        bus: EventBus,
        audio,
        state_machine: GestureStateMachine,
        config: Config,
        camera_worker: CameraWorker,
        gesture_worker: GestureWorker,
        tray: SystemTray,
        overlay: StatusOverlay,
        toast_manager: ToastManager,
    ) -> None:
        super().__init__()
        self._bus = bus
        self._audio = audio
        self._state_machine = state_machine
        self._config = config
        self._camera_worker = camera_worker
        self._gesture_worker = gesture_worker
        self._tray = tray
        self._overlay = overlay
        self._toast_manager = toast_manager
        self._detection_active = True
        self._mic_state = MicState.LIVE

        # Camera -> Gesture (DirectConnection for speed, both are non-main threads)
        self._camera_worker.frame_ready.connect(
            self._gesture_worker.set_frame, Qt.ConnectionType.DirectConnection
        )
        self._camera_worker.error.connect(self._on_camera_error)

        # Gesture -> main thread (AutoConnection = queued since emitter is gesture thread)
        self._gesture_worker.gesture_detected.connect(self._on_gesture)
        self._gesture_worker.no_hand.connect(self._on_no_hand)

        # EventBus mic_action -> audio + UI
        self._bus.subscribe("mic_action", self._on_mic_action)

        # Tray menu actions
        self._tray.toggle_detection_requested.connect(self._toggle_detection)
        self._tray.quit_requested.connect(QApplication.quit)

    def _on_gesture(self, gesture: Gesture, confidence: float) -> None:
        """Handle a detected gesture on the main thread."""
        if not self._detection_active:
            return
        logger.debug("Gesture: %s (%.0f%%)", gesture.name, confidence * 100)
        self._state_machine.on_gesture(gesture, confidence)

    def _on_no_hand(self) -> None:
        """Handle no-hand detection on the main thread."""
        if not self._detection_active:
            return
        self._state_machine.on_no_hand()

    def _on_mic_action(self, action: str, value: int = 0, **_) -> None:
        """Dispatch a mic_action event to audio controller and update UI."""
        match action:
            case "mute":
                self._mic_state = MicState.MUTED
                if self._audio:
                    self._audio.mute()
                logger.info("MIC MUTED")
            case "unmute":
                self._mic_state = MicState.LIVE
                if self._audio:
                    self._audio.unmute()
                logger.info("MIC LIVE")
            case "lock_mute":
                self._mic_state = MicState.LOCKED_MUTE
                if self._audio:
                    self._audio.mute()
                logger.info("MIC LOCKED MUTE")
            case "unlock_mute":
                self._mic_state = MicState.LIVE
                if self._audio:
                    self._audio.unmute()
                logger.info("MIC UNLOCKED -> LIVE")
            case "volume_up":
                if self._audio:
                    self._audio.adjust_volume(value)
                logger.info("VOLUME +%d%%", value)
            case "volume_down":
                if self._audio:
                    self._audio.adjust_volume(-value)
                logger.info("VOLUME -%d%%", value)

        self._tray.update_icon(self._mic_state)
        self._overlay.update_state(self._mic_state)
        self._toast_manager.show_toast(action, self._mic_state)

    def _on_camera_error(self, message: str) -> None:
        """Handle camera errors."""
        logger.error("Camera error: %s", message)

    def _toggle_detection(self) -> None:
        """Pause or resume gesture detection."""
        self._detection_active = not self._detection_active
        if self._detection_active:
            logger.info("Detection resumed")
            self._tray.update_icon(self._mic_state)
            self._overlay.update_state(self._mic_state)
        else:
            logger.info("Detection paused")
            self._tray.update_icon(None)
            self._overlay.update_state(None)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="GestureMute — hands-free mic control")
    parser.add_argument(
        "--preview", action="store_true",
        help="Open a debug preview window showing live camera feed with gesture annotations",
    )
    return parser.parse_args()


def main() -> None:
    """Run the GestureMute PyQt6 application."""
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.preview else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = Config.from_json()
    _ensure_model(config.model_path)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("GestureMute")

    # Core objects
    bus = EventBus()
    audio = _create_audio_controller()
    state_machine = GestureStateMachine(bus, config)

    # Workers (start early so camera warmup + model load happen during UI setup)
    camera_worker = CameraWorker(config)
    gesture_worker = GestureWorker(config)
    camera_worker.start()
    gesture_worker.start()

    # UI
    tray = SystemTray()
    overlay = StatusOverlay()
    toast_manager = ToastManager(overlay, config)

    # Preview window (debug mode)
    preview = None
    if args.preview:
        from gesturemute.ui.preview import PreviewWindow
        preview = PreviewWindow()
        camera_worker.frame_ready.connect(preview.update_frame)
        gesture_worker.gesture_detected.connect(preview.update_gesture)
        gesture_worker.no_hand.connect(preview.update_no_hand)

    # Wire everything
    controller = AppController(
        bus=bus,
        audio=audio,
        state_machine=state_machine,
        config=config,
        camera_worker=camera_worker,
        gesture_worker=gesture_worker,
        tray=tray,
        overlay=overlay,
        toast_manager=toast_manager,
    )

    # Global hotkey (Windows only)
    hotkey = None
    if sys.platform == "win32":
        from gesturemute.ui.hotkey import GlobalHotkey
        hotkey = GlobalHotkey()
        hotkey.triggered.connect(controller._toggle_detection)
        hotkey.start()

    # Start
    tray.show()
    overlay.show()
    if preview is not None:
        preview.show()

    logger.info("GestureMute running in system tray")

    exit_code = app.exec()

    # Cleanup
    logger.info("Shutting down...")
    if hotkey is not None:
        hotkey.stop()
    gesture_worker.stop()
    camera_worker.stop()
    if audio is not None:
        audio.cleanup()
    logger.info("GestureMute stopped.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
