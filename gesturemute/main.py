"""GestureMute entry point — PyQt6 system tray app with webcam gesture recognition."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

# Suppress OpenCV's own stderr spam (backend warnings, property errors).
# Must be set before any cv2 import.
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gesturemute.camera.capture import CameraWorker
    from gesturemute.gesture.engine import GestureWorker

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from gesturemute.config import CONFIG_PATH, Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.gestures import Gesture, MicState
from gesturemute.gesture.state_machine import GestureStateMachine
from gesturemute.ui.onboarding import OnboardingWizard
from gesturemute.ui.toast import ToastManager
from gesturemute.ui.settings import SettingsPanel
from gesturemute.audio.sounds import SoundCuePlayer
from gesturemute.ui.tray import SystemTray

logger = logging.getLogger(__name__)

def _ensure_model(model_path: str) -> None:
    """Download the MediaPipe gesture recognizer model if not present.

    Wraps the shared model.ensure_model() with a Qt error dialog on failure.
    """
    from gesturemute.model import ensure_model
    try:
        ensure_model(model_path)
    except RuntimeError as e:
        QMessageBox.critical(
            None,
            "GestureMute - Download Error",
            f"{e}\n\nCheck your internet connection and try again.",
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
        self._toast_manager = toast_manager
        self._detection_active = True
        self._mic_state = MicState.LIVE
        self._sound_player = None  # Deferred — created after UI is visible

        # Camera -> Gesture (direct callback, both are background threads)
        self._camera_worker.frame_ready.connect(self._gesture_worker.set_frame)
        self._camera_worker.error.connect(self._on_camera_error)

        # Gesture -> main thread (AutoConnection = queued since emitter is gesture thread)
        self._gesture_worker.gesture_detected.connect(self._on_gesture)
        self._gesture_worker.no_hand.connect(self._on_no_hand)

        # EventBus mic_action -> audio + UI
        self._bus.subscribe("mic_action", self._on_mic_action)

        # Settings panel
        self._settings_panel = SettingsPanel(self._config)
        self._tray.settings_requested.connect(self._settings_panel.show)
        self._tray.preview_requested.connect(self._open_preview)
        self._settings_panel.settings_saved.connect(self._on_settings_saved)
        self._settings_panel.preview_requested.connect(self._open_preview)
        self._preview = None
        self._preview_state_cb = None  # EventBus callback ref for cleanup

        # Tray menu actions
        self._tray.toggle_detection_requested.connect(self._toggle_detection)

    def set_audio(self, audio) -> None:
        """Set the audio controller (deferred initialization)."""
        self._audio = audio

    def cleanup(self) -> None:
        """Release resources held by the controller."""
        if self._audio is not None:
            self._audio.cleanup()

    def set_preview(self, preview) -> None:
        """Set and wire up a preview window opened externally (e.g. --preview flag)."""
        self._preview = preview

    def toggle_detection(self) -> None:
        """Public API to pause/resume gesture detection."""
        self._toggle_detection()

    def init_sound_player(self) -> None:
        """Create the SoundCuePlayer (deferred to avoid slowing startup)."""
        self._sound_player = SoundCuePlayer(enabled=self._config.sound_cues_enabled)

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

        if self._sound_player is not None:
            self._sound_player.play(action)
        self._tray.update_icon(self._mic_state)
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
        else:
            logger.info("Detection paused — stopping camera and gesture workers")
            self._gesture_worker.stop()
            self._camera_worker.stop()
            self._state_machine.reset()
            self._tray.update_icon(None)
            if self._preview is not None and self._preview.isVisible():
                self._preview.clear_frame()
        self._tray.update_toggle_label(self._detection_active)

    def _close_preview(self) -> None:
        """Disconnect signals and clean up the preview window."""
        if self._preview is None:
            return
        try:
            self._camera_worker.frame_ready.disconnect(self._preview.update_frame)
            self._gesture_worker.gesture_detected.disconnect(self._preview.update_gesture)
            self._gesture_worker.no_hand.disconnect(self._preview.update_no_hand)
            self._gesture_worker.all_scores.disconnect(self._preview.update_scores)
            self._gesture_worker.landmarks.disconnect(self._preview.update_landmarks)
        except (TypeError, RuntimeError):
            pass
        if self._preview_state_cb is not None:
            self._bus.unsubscribe("state_changed", self._preview_state_cb)
            self._preview_state_cb = None
        self._preview = None

    def _open_preview(self) -> None:
        """Open or raise the debug preview window."""
        if self._preview is not None and self._preview.isVisible():
            self._preview.raise_()
            self._preview.activateWindow()
            return
        # Clean up stale connections from a previously closed preview
        self._close_preview()
        from gesturemute.ui.preview import PreviewWindow
        self._preview = PreviewWindow()
        self._camera_worker.frame_ready.connect(self._preview.update_frame)
        self._gesture_worker.gesture_detected.connect(self._preview.update_gesture)
        self._gesture_worker.no_hand.connect(self._preview.update_no_hand)
        self._gesture_worker.all_scores.connect(self._preview.update_scores)
        self._gesture_worker.landmarks.connect(self._preview.update_landmarks)
        self._preview_state_cb = lambda old_state, new_state, **_: self._preview.update_state(old_state, new_state)
        self._bus.subscribe("state_changed", self._preview_state_cb)
        self._preview.show()

    def _on_settings_saved(self, new_config: Config) -> None:
        """Persist updated configuration to disk."""
        self._config = new_config
        new_config.to_json()
        self._state_machine.update_config(new_config)
        self._settings_panel.update_config(new_config)
        self._camera_worker.update_config(new_config)
        if self._sound_player is not None:
            self._sound_player.set_enabled(new_config.sound_cues_enabled)

        # If detection was paused (no camera) and user just selected one, auto-start
        if not self._detection_active and new_config.camera_name is not None:
            logger.info("Camera selected in settings, starting detection")
            self._detection_active = True
            self._camera_worker.start()
            self._gesture_worker.start()
            self._tray.update_icon(self._mic_state)
            self._tray.update_toggle_label(True)

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
    """Run the GestureMute PyQt6 application.

    Two-phase startup for fast UI visibility (~500ms):
      Phase 1: Config, QApp, onboarding, UI shell (tray/overlay/toast), show + quit signals.
      Phase 2 (deferred): EventBus, workers, AppController, hotkey, audio, sound cues.
    """
    t_start = time.perf_counter()
    print("Starting GestureMute...")
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.preview else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- Phase 1: Show UI as fast as possible ---

    # Preload heavy imports (cv2/numpy/mediapipe) in background thread.
    # Python imports are thread-safe; once loaded they're in sys.modules.
    def _preload_imports():
        t0 = time.perf_counter()
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import mediapipe  # noqa: F401
        logger.info("Background preload done in %.0fms", (time.perf_counter() - t0) * 1000)

    _preload_thread = threading.Thread(target=_preload_imports, daemon=True)
    _preload_thread.start()

    t0 = time.perf_counter()
    config = Config.from_json()
    logger.info("Config loaded in %.0fms", (time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("GestureMute")
    logger.info("QApplication created in %.0fms", (time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    _ensure_model(config.model_path)
    logger.info("Model check in %.0fms", (time.perf_counter() - t0) * 1000)

    # Onboarding wizard (modal, blocks until dismissed)
    if not config.onboarding_completed:
        wizard = OnboardingWizard()
        wizard.exec()
        config.onboarding_completed = True
        config.to_json()

    # Create UI shell (lightweight, no workers needed)
    t0 = time.perf_counter()
    tray = SystemTray()
    toast_manager = ToastManager(config)
    logger.info("UI created in %.0fms", (time.perf_counter() - t0) * 1000)

    # Connect quit signals early so the app can exit during deferred init
    tray.quit_requested.connect(QApplication.quit)

    # UI visible -- Phase 1 complete
    tray.show()
    logger.info("UI visible at %.0fms", (time.perf_counter() - t_start) * 1000)

    # --- Phase 2: Deferred init (next event loop tick) ---

    # Mutable state dict so cleanup can access objects created in _deferred_init
    _app: dict = {
        "controller": None,
        "camera": None,
        "gesture": None,
        "hotkey": None,
    }

    def _deferred_init():
        """Initialize workers, controller, hotkey, and audio on the next event loop tick."""
        t_defer = time.perf_counter()

        # Core objects
        bus = EventBus()
        state_machine = GestureStateMachine(bus, config)

        # Wait for background preload to finish before importing workers
        _preload_thread.join()
        logger.info("Preload join at %.0fms", (time.perf_counter() - t_start) * 1000)

        from gesturemute.camera.capture import CameraWorker
        from gesturemute.gesture.engine import GestureWorker

        # On macOS, resolve camera by unique ID or name (stable across sessions)
        # rather than index (which can shift when devices reconnect).
        should_start_detection = True
        if sys.platform == "darwin":
            from gesturemute.camera.enumerate import (
                find_builtin_camera_index,
                find_first_non_iphone_index,
                get_camera_info,
                get_camera_name,
                resolve_camera_id_to_index,
                resolve_camera_name_to_index,
            )

            if config.camera_unique_id is not None:
                # Best path: resolve by stable unique ID
                resolved = resolve_camera_id_to_index(config.camera_unique_id)
                if resolved is not None:
                    logger.info(
                        "Resolved camera by unique ID to index %d ('%s')",
                        resolved, get_camera_name(resolved),
                    )
                    config.camera_index = resolved
                    config.camera_name = get_camera_name(resolved)
                else:
                    logger.warning(
                        "Saved camera (id=%s, name='%s') not found among connected devices",
                        config.camera_unique_id, config.camera_name,
                    )
                    should_start_detection = False
            elif config.camera_name is not None:
                # Fallback: resolve by name (e.g. migrated from previous version)
                resolved = resolve_camera_name_to_index(config.camera_name)
                if resolved is not None:
                    info = get_camera_info(resolved)
                    config.camera_index = resolved
                    if info:
                        config.camera_unique_id = info[1]
                    logger.info(
                        "Resolved saved camera '%s' to index %d, captured unique ID",
                        config.camera_name, resolved,
                    )
                else:
                    logger.warning(
                        "Saved camera '%s' not found among connected devices",
                        config.camera_name,
                    )
                    should_start_detection = False
            elif config.camera_user_override:
                # Legacy: user selected camera before name/id persistence.
                info = get_camera_info(config.camera_index)
                if info:
                    config.camera_name, config.camera_unique_id = info
                    logger.info(
                        "Migrated legacy camera override: index %d -> '%s' (id=%s)",
                        config.camera_index, config.camera_name, config.camera_unique_id,
                    )
                else:
                    logger.warning(
                        "Legacy camera index %d not found, waiting for user selection",
                        config.camera_index,
                    )
                    should_start_detection = False
            else:
                # Fresh install — auto-select built-in camera
                builtin = find_builtin_camera_index()
                if builtin is not None:
                    config.camera_index = builtin
                    info = get_camera_info(builtin)
                    if info:
                        config.camera_name, config.camera_unique_id = info
                    logger.info(
                        "Auto-selected built-in camera '%s' at index %d",
                        config.camera_name, builtin,
                    )
                else:
                    fallback = find_first_non_iphone_index()
                    if fallback is not None:
                        config.camera_index = fallback
                        info = get_camera_info(fallback)
                        if info:
                            config.camera_name, config.camera_unique_id = info
                        logger.info(
                            "Auto-selected camera '%s' at index %d",
                            config.camera_name, fallback,
                        )
                    else:
                        logger.warning("No cameras found at startup")
                        should_start_detection = False

            # All paths above set config.camera_index to the AVFoundation index,
            # which may differ from the OpenCV index. Fingerprint to find the
            # correct OpenCV index for the target device.
            if should_start_detection and config.camera_unique_id:
                from gesturemute.camera.enumerate import find_opencv_index_for_device
                opencv_idx = find_opencv_index_for_device(config.camera_unique_id)
                if opencv_idx is not None:
                    if opencv_idx != config.camera_index:
                        logger.info(
                            "Fingerprint: AVFoundation index %d → OpenCV index %d for '%s'",
                            config.camera_index, opencv_idx, config.camera_name,
                        )
                    config.camera_index = opencv_idx
                else:
                    logger.warning(
                        "Fingerprinting failed for '%s', using AVFoundation index %d",
                        config.camera_name, config.camera_index,
                    )

            # Verify the resolved camera can produce a frame.
            if should_start_detection:
                import cv2
                _probe = cv2.VideoCapture(config.camera_index)
                _probe_ok = False
                if _probe.isOpened():
                    _ret, _ = _probe.read()
                    _probe_ok = _ret
                _probe.release()

                if not _probe_ok:
                    logger.error(
                        "Camera '%s' at OpenCV index %d failed to produce a frame",
                        config.camera_name, config.camera_index,
                    )
                    should_start_detection = False

            # Persist resolved camera_name for next session
            config.to_json()

        camera_worker = CameraWorker(config)
        gesture_worker = GestureWorker(config)
        _app["camera"] = camera_worker
        _app["gesture"] = gesture_worker
        logger.info("Workers created at %.0fms", (time.perf_counter() - t_start) * 1000)

        # Wire everything (audio=None initially, deferred further below)
        controller = AppController(
            bus=bus,
            audio=None,
            state_machine=state_machine,
            config=config,
            camera_worker=camera_worker,
            gesture_worker=gesture_worker,
            tray=tray,
            toast_manager=toast_manager,
        )
        _app["controller"] = controller

        # Preview window (debug mode)
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
            controller.set_preview(preview)
            preview.show()

        # Global hotkey
        from gesturemute.ui.hotkey import create_global_hotkey
        hotkey = create_global_hotkey()
        if hotkey is not None:
            hotkey.triggered.connect(controller.toggle_detection)
            if hasattr(hotkey, "failed"):
                hotkey.failed.connect(
                    lambda msg: tray.show_message(
                        "GestureMute", msg,
                        QSystemTrayIcon.MessageIcon.Warning, 5000,
                    )
                )
            hotkey.start()
            _app["hotkey"] = hotkey

        # Track readiness for startup timing
        _ready_state = {"camera": False, "engine": False}

        def _on_camera_ready():
            _ready_state["camera"] = True
            logger.info("Camera ready at %.0fms", (time.perf_counter() - t_start) * 1000)
            if _ready_state["engine"]:
                _log_fully_functional()

        def _on_engine_ready():
            _ready_state["engine"] = True
            logger.info("Gesture engine ready at %.0fms", (time.perf_counter() - t_start) * 1000)
            if _ready_state["camera"]:
                _log_fully_functional()

        def _log_fully_functional():
            elapsed = (time.perf_counter() - t_start) * 1000
            logger.info("Fully functional at %.0fms after launch", elapsed)
            print(f"GestureMute ready ({elapsed:.0f}ms)")

        camera_worker.camera_ready.connect(_on_camera_ready)
        gesture_worker.engine_ready.connect(_on_engine_ready)

        # Start workers (after signal connections to avoid missing early emissions)
        if should_start_detection:
            camera_worker.start()
            gesture_worker.start()
            logger.info("Workers started at %.0fms", (time.perf_counter() - t_start) * 1000)
        else:
            # No camera resolved — start paused and prompt user
            controller._detection_active = False
            tray.update_icon(None)
            tray.update_toggle_label(False)
            if config.camera_name is not None:
                tray.show_message(
                    "GestureMute",
                    f"Camera '{config.camera_name}' not found. Select a camera in Settings.",
                    QSystemTrayIcon.MessageIcon.Warning, 5000,
                )
            else:
                tray.show_message(
                    "GestureMute",
                    "Select a camera in Settings to start detection.",
                    QSystemTrayIcon.MessageIcon.Information, 5000,
                )
            logger.info("Started paused — no camera resolved")

        # Defer audio and sound cues to subsequent event loop ticks
        def _init_audio():
            audio = _create_audio_controller()
            controller.set_audio(audio)
            if audio is None and sys.platform in ("win32", "darwin"):
                logger.warning("Audio controller unavailable -- app will run without mic control")
                toast_manager.show_toast("warning", None, value=0)
            else:
                logger.info("Audio controller initialized")

        QTimer.singleShot(0, _init_audio)
        QTimer.singleShot(0, controller.init_sound_player)

        logger.info(
            "Deferred init complete in %.0fms (total %.0fms)",
            (time.perf_counter() - t_defer) * 1000,
            (time.perf_counter() - t_start) * 1000,
        )

    QTimer.singleShot(0, _deferred_init)
    logger.info("GestureMute running in system tray")

    exit_code = app.exec()

    # Cleanup — use public stop() methods which set _running=False and wait()
    logger.info("Shutting down...")
    if _app["hotkey"] is not None:
        _app["hotkey"].stop()
    if _app["gesture"] is not None:
        _app["gesture"].stop()
    if _app["camera"] is not None:
        _app["camera"].stop()
    if _app["controller"] is not None:
        _app["controller"].cleanup()
    logger.info("GestureMute stopped.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
