"""GestureMute subprocess bridge — stdin/stdout JSON IPC.

Entry point for running the gesture engine as a headless subprocess
controlled by a native SwiftUI app. No PyQt6 dependencies.
"""

import json
import logging
import os
import sys
import threading
import time

# Suppress OpenCV stderr spam before any cv2 import.
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.gestures import Gesture, GestureState, MicState
from gesturemute.gesture.state_machine import GestureStateMachine

logger = logging.getLogger(__name__)


class JsonBridge:
    """Bidirectional JSON-line IPC over stdin/stdout."""

    def __init__(self) -> None:
        self._write_lock = threading.Lock()
        self._handlers: dict[str, callable] = {}
        self._running = False

    def send(self, msg_type: str, payload: dict | None = None) -> None:
        """Write a JSON message to stdout (thread-safe)."""
        msg: dict = {"type": msg_type}
        if payload is not None:
            msg["payload"] = payload
        with self._write_lock:
            sys.stdout.write(json.dumps(msg) + "\n")
            sys.stdout.flush()

    def register(self, msg_type: str, handler: callable) -> None:
        """Register a handler for an incoming message type."""
        self._handlers[msg_type] = handler

    def run_stdin_loop(self) -> None:
        """Blocking stdin reader — run in a dedicated thread."""
        self._running = True
        try:
            for line in sys.stdin:
                if not self._running:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    msg_type = msg.get("type")
                    handler = self._handlers.get(msg_type)
                    if handler:
                        handler(msg.get("payload") or {})
                    else:
                        logger.warning("Unknown message type: %s", msg_type)
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON on stdin: %s", e)
                except Exception:
                    logger.exception("Error processing stdin message")
        except Exception:
            logger.exception("Fatal error in stdin loop")
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the stdin loop to stop."""
        self._running = False


class EngineController:
    """Manages camera + gesture workers and translates events to JSON.

    Mirrors the wiring in main.py's AppController but without any PyQt6.
    """

    def __init__(self, bridge: JsonBridge, config: Config) -> None:
        self._bridge = bridge
        self._config = config
        self._bus = EventBus()
        self._state_machine = GestureStateMachine(self._bus, config)
        self._mic_state = MicState.LIVE
        self._detection_active = False
        self._camera_worker = None
        self._gesture_worker = None
        self._audio = None

        # Subscribe to EventBus events
        self._bus.subscribe("mic_action", self._on_mic_action)
        self._bus.subscribe("state_changed", self._on_state_changed)

        # Register IPC command handlers
        bridge.register("start_detection", lambda p: self.start_detection())
        bridge.register("stop_detection", lambda p: self.stop_detection())
        bridge.register("update_config", self._on_update_config)
        bridge.register("list_cameras", lambda p: self._send_camera_list())
        bridge.register("get_status", lambda p: self._send_status())
        bridge.register("get_config", lambda p: self._send_config())
        bridge.register("shutdown", lambda p: self.shutdown())

    def initialize(self) -> None:
        """Initialize workers and audio (deferred from __init__ for timing)."""
        from gesturemute.camera.capture import CameraWorker
        from gesturemute.gesture.engine import GestureWorker

        self._camera_worker = CameraWorker(self._config)
        self._gesture_worker = GestureWorker(self._config)

        # Camera -> Gesture: direct callback (both are background threads)
        self._camera_worker.frame_ready.connect(self._gesture_worker.set_frame)
        self._camera_worker.error.connect(
            lambda msg: self._bridge.send("error", {"source": "camera", "message": msg})
        )
        self._camera_worker.camera_ready.connect(
            lambda: self._bridge.send("camera_ready")
        )
        self._camera_worker.camera_lost.connect(
            lambda: self._bridge.send("camera_lost")
        )
        self._camera_worker.camera_restored.connect(
            lambda: self._bridge.send("camera_restored")
        )

        # Gesture -> bridge events
        self._gesture_worker.gesture_detected.connect(self._on_gesture)
        self._gesture_worker.no_hand.connect(self._on_no_hand)
        self._gesture_worker.engine_ready.connect(
            lambda: self._bridge.send("engine_ready")
        )

        # Audio controller
        self._audio = self._create_audio_controller()

        self._bridge.send("bridge_ready")

    def _create_audio_controller(self):
        """Create the platform-appropriate audio controller."""
        try:
            if sys.platform == "darwin":
                from gesturemute.audio.macos import MacOSAudioController
                return MacOSAudioController()
            else:
                logger.warning("No audio controller for platform %s", sys.platform)
                return None
        except Exception:
            logger.exception("Failed to initialize audio controller")
            return None

    def start_detection(self) -> None:
        """Start camera and gesture workers."""
        if self._detection_active:
            return
        if self._camera_worker is None:
            self.initialize()

        # Resolve camera on macOS
        self._resolve_camera()

        self._camera_worker.start()
        self._gesture_worker.start()
        self._detection_active = True
        self._bridge.send("detection_started")
        logger.info("Detection started")

    def stop_detection(self) -> None:
        """Stop camera and gesture workers."""
        if not self._detection_active:
            return
        self._detection_active = False
        if self._gesture_worker:
            self._gesture_worker.stop()
        if self._camera_worker:
            self._camera_worker.stop()
        self._state_machine.reset()
        self._bridge.send("detection_stopped")
        logger.info("Detection stopped")

    def shutdown(self) -> None:
        """Graceful shutdown — stop workers and exit."""
        logger.info("Shutdown requested")
        self.stop_detection()
        if self._audio:
            self._audio.cleanup()
        # Exit will be handled by the main loop ending
        os._exit(0)

    def _resolve_camera(self) -> None:
        """Resolve camera by unique ID or name on macOS."""
        if sys.platform != "darwin":
            return

        from gesturemute.camera.enumerate import (
            find_builtin_camera_index,
            find_first_non_iphone_index,
            find_opencv_index_for_device,
            get_camera_info,
            get_camera_name,
            resolve_camera_id_to_index,
            resolve_camera_name_to_index,
        )

        if self._config.camera_unique_id is not None:
            resolved = resolve_camera_id_to_index(self._config.camera_unique_id)
            if resolved is not None:
                self._config.camera_index = resolved
                self._config.camera_name = get_camera_name(resolved)
            else:
                logger.warning("Saved camera (id=%s) not found", self._config.camera_unique_id)
                return
        elif self._config.camera_name is not None:
            resolved = resolve_camera_name_to_index(self._config.camera_name)
            if resolved is not None:
                info = get_camera_info(resolved)
                self._config.camera_index = resolved
                if info:
                    self._config.camera_unique_id = info[1]
            else:
                logger.warning("Saved camera '%s' not found", self._config.camera_name)
                return
        else:
            # Auto-select built-in camera
            builtin = find_builtin_camera_index()
            if builtin is not None:
                self._config.camera_index = builtin
                info = get_camera_info(builtin)
                if info:
                    self._config.camera_name, self._config.camera_unique_id = info
            else:
                fallback = find_first_non_iphone_index()
                if fallback is not None:
                    self._config.camera_index = fallback
                    info = get_camera_info(fallback)
                    if info:
                        self._config.camera_name, self._config.camera_unique_id = info
                else:
                    logger.warning("No cameras found")
                    return

        # Update worker with resolved config
        # (resolve_camera_id_to_index already fingerprinted the correct OpenCV index)
        self._camera_worker.update_config(self._config)

    def _on_gesture(self, gesture: Gesture, confidence: float) -> None:
        """Handle detected gesture."""
        if not self._detection_active:
            return
        self._state_machine.on_gesture(gesture, confidence)
        self._bridge.send("gesture_detected", {
            "gesture": gesture.name,
            "confidence": round(confidence, 3),
        })

    def _on_no_hand(self) -> None:
        """Handle no-hand detection."""
        if not self._detection_active:
            return
        self._state_machine.on_no_hand()

    def _on_mic_action(self, action: str, value: int = 0, **_) -> None:
        """Handle mic_action from state machine — control audio and notify Swift."""
        match action:
            case "mute":
                self._mic_state = MicState.MUTED
                if self._audio:
                    self._audio.mute()
            case "unmute":
                self._mic_state = MicState.LIVE
                if self._audio:
                    self._audio.unmute()
            case "lock_mute":
                self._mic_state = MicState.LOCKED_MUTE
                if self._audio:
                    self._audio.mute()
            case "unlock_mute":
                self._mic_state = MicState.LIVE
                if self._audio:
                    self._audio.unmute()
            case "volume_up":
                actual = self._audio.adjust_volume(value) if self._audio else 0
                value = actual
            case "volume_down":
                actual = self._audio.adjust_volume(-value) if self._audio else 0
                value = actual
            case "pause_detection":
                # Run on a separate thread — this callback fires on the gesture
                # worker thread, and stop_detection() tries to join that thread.
                threading.Thread(target=self.stop_detection, daemon=True).start()
                return

        self._bridge.send("mic_action", {
            "action": action,
            "value": value,
            "mic_state": self._mic_state.name,
        })

    def _on_state_changed(self, old_state: GestureState, new_state: GestureState, **_) -> None:
        """Forward state machine transitions to Swift."""
        self._bridge.send("state_changed", {
            "old_state": old_state.name,
            "new_state": new_state.name,
        })

    def _on_update_config(self, payload: dict) -> None:
        """Apply new configuration from Swift."""
        try:
            # Merge payload into current config
            from dataclasses import asdict
            current = asdict(self._config)
            current.update(payload)
            # Remove config_version from merge to avoid overwrite
            current.pop("config_version", None)
            self._config = Config(**current)
            self._config.to_json()

            self._state_machine.update_config(self._config)
            if self._camera_worker:
                self._camera_worker.update_config(self._config)

            self._bridge.send("config", self._config_to_dict())
            logger.info("Config updated from Swift")
        except Exception:
            logger.exception("Failed to update config")
            self._bridge.send("error", {"source": "config", "message": "Failed to update config"})

    def _send_camera_list(self) -> None:
        """Send available cameras to Swift."""
        cameras = []
        try:
            if sys.platform == "darwin":
                from gesturemute.camera.enumerate import list_cameras_full
                for idx, name, uid in list_cameras_full():
                    is_builtin = "built-in" in name.lower() or "facetime" in name.lower()
                    cameras.append({
                        "index": idx,
                        "name": name,
                        "unique_id": uid,
                        "is_builtin": is_builtin,
                    })
        except Exception:
            logger.exception("Failed to enumerate cameras")

        self._bridge.send("camera_list", {"cameras": cameras})

    def _send_status(self) -> None:
        """Send current engine status to Swift."""
        self._bridge.send("status", {
            "detection_active": self._detection_active,
            "mic_state": self._mic_state.name,
            "gesture_state": self._state_machine.state.name,
            "camera_name": self._config.camera_name,
        })

    def _send_config(self) -> None:
        """Send current config to Swift."""
        self._bridge.send("config", self._config_to_dict())

    def _config_to_dict(self) -> dict:
        """Convert config to a JSON-safe dict."""
        from dataclasses import asdict
        return asdict(self._config)


def main() -> None:
    """Run the GestureMute engine as a subprocess with JSON IPC."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # Logs go to stderr, JSON goes to stdout
    )

    logger.info("GestureMute engine starting (bridge mode)")

    config = Config.from_json()
    bridge = JsonBridge()
    controller = EngineController(bridge, config)

    # Ensure model is available
    from gesturemute.model import ensure_model
    try:
        ensure_model(config.model_path)
    except RuntimeError as e:
        bridge.send("error", {"source": "model", "message": str(e)})
        sys.exit(1)

    # Initialize workers (deferred heavy imports)
    controller.initialize()

    # Run stdin loop on main thread (blocks until stdin closes or shutdown)
    logger.info("Bridge ready, waiting for commands on stdin")
    bridge.run_stdin_loop()

    # If stdin closes, shut down gracefully
    logger.info("Stdin closed, shutting down")
    controller.stop_detection()
    if controller._audio:
        controller._audio.cleanup()


if __name__ == "__main__":
    main()
