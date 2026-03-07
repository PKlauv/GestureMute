"""GestureMute entry point — webcam gesture recognition for mic control."""

import argparse
import logging
import sys
import time
import urllib.request
from pathlib import Path

import cv2

from gesturemute.camera.capture import Camera
from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.engine import GestureEngine
from gesturemute.gesture.gestures import Gesture
from gesturemute.gesture.state_machine import GestureStateMachine

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


def _handle_mic_action(audio, action: str, value: int = 0) -> None:
    """Dispatch a mic_action event to the audio controller."""
    if audio is None:
        print(f"[dry-run] mic_action: {action} (value={value})")
        return

    match action:
        case "mute":
            audio.mute()
            print("MIC MUTED")
        case "unmute":
            audio.unmute()
            print("MIC LIVE")
        case "lock_mute":
            audio.mute()
            print("MIC LOCKED MUTE")
        case "unlock_mute":
            audio.unmute()
            print("MIC UNLOCKED -> LIVE")
        case "volume_up":
            audio.adjust_volume(value)
            print(f"VOLUME +{value}%")
        case "volume_down":
            audio.adjust_volume(-value)
            print(f"VOLUME -{value}%")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="GestureMute — hands-free mic control via webcam gestures")
    parser.add_argument(
        "--preview", action="store_true",
        help="Open a debug window showing the webcam feed with gesture overlay",
    )
    return parser.parse_args()


# Colors for preview overlay (BGR format for OpenCV)
_COLOR_GREEN = (129, 185, 16)   # MIC_LIVE #10B981 in BGR
_COLOR_RED = (96, 69, 233)      # MIC_MUTED #E94560 in BGR
_COLOR_WHITE = (255, 255, 255)


def _draw_preview(
    frame,
    last_gesture: str,
    last_confidence: float,
    state_name: str,
    mic_status: str,
) -> None:
    """Draw debug overlay on the frame and show it in a window."""
    h, w = frame.shape[:2]

    # Semi-transparent background bar at top
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Line 1: Gesture + confidence
    gesture_text = f"{last_gesture} {last_confidence:.0%}" if last_gesture != "NONE" else "No gesture"
    cv2.putText(frame, gesture_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, _COLOR_WHITE, 2)

    # Line 2: State machine state
    cv2.putText(frame, f"State: {state_name}", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _COLOR_WHITE, 1)

    # Line 3: Mic status
    is_muted = "MUTE" in mic_status
    mic_color = _COLOR_RED if is_muted else _COLOR_GREEN
    cv2.putText(frame, f"MIC: {mic_status}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mic_color, 2)

    # Status dot in top-right corner
    cv2.circle(frame, (w - 25, 25), 12, mic_color, -1)

    cv2.imshow("GestureMute Debug", frame)


def main() -> None:
    """Run the GestureMute main loop."""
    args = _parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = Config.from_json()
    _ensure_model(config.model_path)

    bus = EventBus()
    audio = _create_audio_controller()
    state_machine = GestureStateMachine(bus, config)
    engine = GestureEngine(config)
    camera = Camera(config)

    # Track mic status for overlay display
    mic_status = "LIVE"

    def handle_mic_action_wrapper(**kw):
        nonlocal mic_status
        action = kw.get("action", "")
        match action:
            case "mute":
                mic_status = "MUTED"
            case "unmute":
                mic_status = "LIVE"
            case "lock_mute":
                mic_status = "LOCKED MUTE"
            case "unlock_mute":
                mic_status = "LIVE"
        _handle_mic_action(audio, **kw)

    # Wire events
    bus.subscribe("mic_action", handle_mic_action_wrapper)
    bus.subscribe(
        "state_changed",
        lambda old_state, new_state, **_: print(f"  [{old_state.name} -> {new_state.name}]"),
    )

    camera.open()
    print("GestureMute running. Press Ctrl+C to quit.")
    if args.preview:
        print("Preview window active. Press 'q' in the window to quit.")
    print("Hold open palm to mute, release to unmute.")
    print("Palm -> Fist to lock mute. Thumbs up/down for volume.\n")

    # State for logging and overlay
    last_gesture_name = "NONE"
    last_confidence = 0.0
    last_no_hand_log_ms = 0.0

    try:
        while True:
            success, frame, timestamp_ms = camera.read_frame()
            if not success:
                time.sleep(0.01)
                continue

            if camera.should_process():
                engine.process_frame(frame, timestamp_ms)

            # Process any gesture results from the async callback
            results = engine.drain_results()
            for gesture, confidence in results:
                if gesture == Gesture.NONE:
                    # Throttle no-hand logging to every ~2s
                    now_ms = time.monotonic_ns() / 1_000_000
                    if last_gesture_name != "NONE" or (now_ms - last_no_hand_log_ms) >= 2000:
                        logger.debug("No hand detected")
                        last_no_hand_log_ms = now_ms
                    last_gesture_name = "NONE"
                    last_confidence = 0.0
                    state_machine.on_no_hand()
                else:
                    last_gesture_name = gesture.name
                    last_confidence = confidence
                    print(f"  Gesture: {gesture.name} ({confidence:.0%})")
                    state_machine.on_gesture(gesture, confidence)

            # Preview window
            if args.preview and frame is not None:
                _draw_preview(
                    frame,
                    last_gesture_name,
                    last_confidence,
                    state_machine.state.name,
                    mic_status,
                )
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("\nQuitting via preview window...")
                    break

            del frame

            # Small sleep to prevent busy-waiting
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        engine.close()
        camera.close()
        if args.preview:
            cv2.destroyAllWindows()
        if audio is not None:
            audio.cleanup()
        print("GestureMute stopped.")


if __name__ == "__main__":
    main()
