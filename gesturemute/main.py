"""GestureMute entry point — PyQt6 system tray app with webcam gesture recognition."""

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from gesturemute.camera.capture import CameraWorker
from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.engine import GestureWorker
from gesturemute.gesture.gestures import Gesture, MicState
from gesturemute.gesture.state_machine import GestureStateMachine
from gesturemute.ui.onboarding import OnboardingWizard
from gesturemute.ui.overlay import StatusOverlay
from gesturemute.ui.toast import ToastManager
from gesturemute.ui.settings import SettingsPanel
from gesturemute.audio.sounds import SoundCuePlayer
from gesturemute.ui.tray import SystemTray

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
)


def _ensure_model(model_path: str) -> None:
    """Download the MediaPipe gesture recognizer model if not present.

    Downloads with a 60s timeout, retries once on failure. Raises SystemExit
    if the model cannot be obtained.

    Args:
        model_path: Path where the model file should exist.
    """
    path = Path(model_path)
    if path.exists():
        if path.stat().st_size > 0:
            return
        # Empty/corrupt model file — remove and re-download
        logger.warning("Model file at %s is empty, re-downloading", path)
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(2):
        try:
            print(f"Downloading gesture model to {path} (attempt {attempt + 1})...")
            urllib.request.urlretrieve(MODEL_URL, path, _reporthook=None)
            print("Download complete.")
            return
        except Exception as e:
            logger.warning("Model download attempt %d failed: %s", attempt + 1, e)
            if path.exists():
                path.unlink()
            if attempt == 0:
                continue
            # Both attempts failed
            QMessageBox.critical(
                None,
                "GestureMute - Download Error",
                f"Failed to download gesture model after 2 attempts:\n{e}\n\n"
                "Check your internet connection and try again.",
            )
            sys.exit(1)


def _create_audio_controller():
    """Create the platform-appropriate audio controller.

    Returns None on unsupported platforms or if initialization fails.
    """
    try:
        if sys.platform == "win32":
            from gesturemute.audio.windows import WindowsAudioController
            return WindowsAudioController()
        elif sys.platform == "darwin":
            from gesturemute.audio.macos import MacOSAudioController
            return MacOSAudioController()
        else:
            logger.warning("No audio controller for platform %s", sys.platform)
            return None
    except Exception as e:
        logger.exception("Failed to initialize audio controller")
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
        self._sound_player = SoundCuePlayer(enabled=config.sound_cues_enabled)

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

        # Settings panel
        self._settings_panel = SettingsPanel(self._config)
        self._tray.settings_requested.connect(self._settings_panel.show)
        self._overlay.clicked.connect(self._settings_panel.show)
        self._overlay.settings_requested.connect(self._settings_panel.show)
        self._overlay.quit_requested.connect(QApplication.quit)
        self._settings_panel.settings_saved.connect(self._on_settings_saved)
        self._settings_panel.preview_requested.connect(self._open_preview)
        self._preview = None

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
                actual = self._audio.adjust_volume(value) if self._audio else 0
                value = actual
                logger.info("VOLUME +%d%% (now %d%%)", self._config.volume_step, actual)
            case "volume_down":
                actual = self._audio.adjust_volume(-value) if self._audio else 0
                value = actual
                logger.info("VOLUME -%d%% (now %d%%)", self._config.volume_step, actual)
            case "pause_detection":
                if self._detection_active:
                    self._toast_manager.show_toast(action, self._mic_state, value=value)
                    self._toggle_detection()
                return

        self._sound_player.play(action)
        self._tray.update_icon(self._mic_state)
        self._overlay.update_state(self._mic_state)
        self._toast_manager.show_toast(action, self._mic_state, value=value)

    def _on_camera_error(self, message: str) -> None:
        """Handle camera errors."""
        logger.error("Camera error: %s", message)

    def _toggle_detection(self) -> None:
        """Pause or resume gesture detection by stopping/starting worker threads."""
        self._detection_active = not self._detection_active
        if self._detection_active:
            logger.info("Detection resumed — starting camera and gesture workers")
            self._camera_worker.start()
            self._gesture_worker.start()
            if self._preview is not None and self._preview.isVisible():
                self._preview.resume()
            self._tray.update_icon(self._mic_state)
            self._overlay.update_state(self._mic_state)
        else:
            logger.info("Detection paused — stopping camera and gesture workers")
            self._gesture_worker.stop()
            self._camera_worker.stop()
            self._state_machine.reset()
            self._tray.update_icon(None)
            self._overlay.update_state(None)
            if self._preview is not None and self._preview.isVisible():
                self._preview.clear_frame()

    def _open_preview(self) -> None:
        """Open or raise the debug preview window."""
        if self._preview is not None and self._preview.isVisible():
            self._preview.raise_()
            self._preview.activateWindow()
            return
        from gesturemute.ui.preview import PreviewWindow
        self._preview = PreviewWindow()
        self._camera_worker.frame_ready.connect(self._preview.update_frame)
        self._gesture_worker.gesture_detected.connect(self._preview.update_gesture)
        self._gesture_worker.no_hand.connect(self._preview.update_no_hand)
        self._gesture_worker.all_scores.connect(self._preview.update_scores)
        self._gesture_worker.landmarks.connect(self._preview.update_landmarks)
        self._bus.subscribe(
            "state_changed",
            lambda old_state, new_state, **_: self._preview.update_state(old_state, new_state),
        )
        self._preview.show()

    def _on_settings_saved(self, new_config: Config) -> None:
        """Persist updated configuration to disk."""
        new_config.overlay_x = self._overlay.x()
        new_config.overlay_y = self._overlay.y()
        self._config = new_config
        new_config.to_json()
        self._state_machine.update_config(new_config)
        self._settings_panel.update_config(new_config)
        self._overlay.set_style(new_config.overlay_style)
        self._camera_worker.update_config(new_config)
        self._sound_player.set_enabled(new_config.sound_cues_enabled)
        logger.info("Settings saved")


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

    # Onboarding wizard (modal, blocks until dismissed)
    if not config.onboarding_completed:
        wizard = OnboardingWizard()
        wizard.exec()
        config.onboarding_completed = True
        config.to_json()

    # Core objects
    bus = EventBus()
    state_machine = GestureStateMachine(bus, config)

    # Workers (start early so camera warmup + model load happen during UI setup)
    camera_worker = CameraWorker(config)
    gesture_worker = GestureWorker(config)
    camera_worker.start()
    gesture_worker.start()

    # UI
    tray = SystemTray()
    overlay = StatusOverlay()
    overlay.set_style(config.overlay_style)
    overlay.restore_position(config)
    toast_manager = ToastManager(overlay, config)

    # Preview window (debug mode)
    preview = None
    if args.preview:
        from gesturemute.ui.preview import PreviewWindow
        preview = PreviewWindow()
        camera_worker.frame_ready.connect(preview.update_frame)
        gesture_worker.gesture_detected.connect(preview.update_gesture)
        gesture_worker.no_hand.connect(preview.update_no_hand)
        gesture_worker.all_scores.connect(preview.update_scores)
        gesture_worker.landmarks.connect(preview.update_landmarks)
        bus.subscribe(
            "state_changed",
            lambda old_state, new_state, **_: preview.update_state(old_state, new_state),
        )

    # Wire everything (audio=None initially, deferred for faster startup)
    controller = AppController(
        bus=bus,
        audio=None,
        state_machine=state_machine,
        config=config,
        camera_worker=camera_worker,
        gesture_worker=gesture_worker,
        tray=tray,
        overlay=overlay,
        toast_manager=toast_manager,
    )

    if preview is not None:
        controller._preview = preview

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

    # Defer audio controller init until after UI is visible for faster startup
    def _init_audio():
        controller._audio = _create_audio_controller()
        if controller._audio is None and sys.platform in ("win32", "darwin"):
            logger.warning("Audio controller unavailable — app will run without mic control")
            toast_manager.show_toast("warning", None, value=0)
        else:
            logger.info("Audio controller initialized")

    QTimer.singleShot(0, _init_audio)

    logger.info("GestureMute running in system tray")

    exit_code = app.exec()

    # Cleanup
    _SHUTDOWN_TIMEOUT_MS = 3000
    logger.info("Shutting down...")
    if hotkey is not None:
        hotkey.stop()
    gesture_worker._running = False
    camera_worker._running = False
    if not gesture_worker.wait(_SHUTDOWN_TIMEOUT_MS):
        logger.warning("Gesture worker did not stop within %dms", _SHUTDOWN_TIMEOUT_MS)
    if not camera_worker.wait(_SHUTDOWN_TIMEOUT_MS):
        logger.warning("Camera worker did not stop within %dms", _SHUTDOWN_TIMEOUT_MS)
    if controller._audio is not None:
        controller._audio.cleanup()
    logger.info("GestureMute stopped.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
