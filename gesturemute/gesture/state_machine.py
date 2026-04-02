"""Gesture state machine with cooldown and activation delay."""

import logging
import time

from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.gestures import Gesture, GestureState

logger = logging.getLogger(__name__)


class GestureStateMachine:
    """Manages gesture-to-action state transitions.

    Enforces cooldown between transitions, activation delay for palm mute,
    and no-hand timeout. Emits mic_action and state_changed events on the bus.

    Args:
        bus: Event bus for emitting actions.
        config: Application configuration.
    """

    def __init__(self, bus: EventBus, config: Config) -> None:
        self._bus = bus
        self._config = config
        self._state = GestureState.IDLE
        self._last_transition_ms: float = 0
        self._palm_start_ms: float | None = None
        self._palm_mute_active = False
        self._last_hand_seen_ms: float = self._now_ms()
        self._grace_start_ms: float | None = None
        self._volume_return_state: GestureState = GestureState.IDLE
        self._last_volume_emit_ms: float = 0

    def reset(self) -> None:
        """Reset state machine to idle, clearing all pending timers."""
        self._state = GestureState.IDLE
        self._last_transition_ms = 0
        self._palm_start_ms = None
        self._palm_mute_active = False
        self._last_hand_seen_ms = self._now_ms()
        self._grace_start_ms = None
        self._volume_return_state = GestureState.IDLE
        self._last_volume_emit_ms = 0
        logger.info("State machine reset to IDLE")

    def update_config(self, config: Config) -> None:
        """Update configuration (e.g. after settings change)."""
        self._config = config

    @staticmethod
    def _now_ms() -> float:
        """Return current time in milliseconds using monotonic clock."""
        return time.monotonic_ns() / 1_000_000

    @property
    def state(self) -> GestureState:
        """Current gesture state."""
        return self._state

    def _set_state(self, new_state: GestureState) -> None:
        """Transition to a new state and emit state_changed event."""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            self._last_transition_ms = self._now_ms()
            self._grace_start_ms = None
            logger.info("State: %s -> %s", old_state.name, new_state.name)
            self._bus.emit(
                "state_changed",
                old_state=old_state,
                new_state=new_state,
            )

    def _grace_expired(self) -> bool:
        """Return True if grace period has been started and has expired."""
        if self._grace_start_ms is None:
            return False
        return (self._now_ms() - self._grace_start_ms) >= self._config.transition_grace_ms

    def _start_grace(self) -> None:
        """Start the grace timer if not already running."""
        if self._grace_start_ms is None:
            self._grace_start_ms = self._now_ms()

    def _cooldown_ok(self) -> bool:
        """Return True if enough time has passed since last transition."""
        return (self._now_ms() - self._last_transition_ms) >= self._config.gesture_cooldown_ms

    def on_gesture(self, gesture: Gesture, confidence: float) -> None:
        """Process a detected gesture through the state machine.

        Args:
            gesture: The recognized gesture.
            confidence: Confidence score from MediaPipe (0.0-1.0).
        """
        now = self._now_ms()
        self._last_hand_seen_ms = now

        threshold = self._config.confidence_thresholds.get(
            gesture.to_label(), self._config.confidence_threshold
        )
        # Lower Closed_Fist threshold during PALM_HOLD for more forgiving transition
        if self._state == GestureState.PALM_HOLD and gesture == Gesture.CLOSED_FIST:
            threshold *= 0.7
        if confidence < threshold:
            return

        # TWO_FISTS_CLOSE is a meta-gesture that pauses detection from any state
        if gesture == Gesture.TWO_FISTS_CLOSE and self._cooldown_ok():
            self._last_transition_ms = self._now_ms()
            self._bus.emit("mic_action", action="pause_detection")
            return

        match self._state:
            case GestureState.IDLE:
                self._handle_idle(gesture, now)
            case GestureState.PALM_HOLD:
                self._handle_palm_hold(gesture, now)
            case GestureState.MUTE_LOCKED:
                self._handle_mute_locked(gesture)
            case GestureState.FIST_PENDING_UNLOCK:
                self._handle_fist_pending_unlock(gesture)
            case GestureState.VOLUME_UP:
                self._handle_volume(gesture, self._config.volume_step)
            case GestureState.VOLUME_DOWN:
                self._handle_volume(gesture, -self._config.volume_step)

    def on_no_hand(self) -> None:
        """Handle the absence of a detected hand."""
        now = self._now_ms()
        elapsed = now - self._last_hand_seen_ms

        match self._state:
            case GestureState.PALM_HOLD:
                self._start_grace()
                if self._grace_expired():
                    if self._palm_mute_active:
                        self._bus.emit("mic_action", action="unmute")
                        self._palm_mute_active = False
                    self._palm_start_ms = None
                    self._set_state(GestureState.IDLE)

            case GestureState.MUTE_LOCKED:
                # Lock mute persists — do nothing
                pass

            case GestureState.FIST_PENDING_UNLOCK:
                self._start_grace()
                if self._grace_expired():
                    self._set_state(GestureState.MUTE_LOCKED)

            case GestureState.VOLUME_UP | GestureState.VOLUME_DOWN:
                self._set_state(self._volume_return_state)

            case GestureState.IDLE:
                pass

    def _handle_idle(self, gesture: Gesture, now: float) -> None:
        """Handle gestures while in IDLE state."""
        match gesture:
            case Gesture.OPEN_PALM:
                if self._cooldown_ok():
                    self._palm_start_ms = now
                    self._palm_mute_active = False
                    self._set_state(GestureState.PALM_HOLD)
            case Gesture.THUMB_UP:
                self._volume_return_state = GestureState.IDLE
                self._last_volume_emit_ms = self._now_ms()
                self._set_state(GestureState.VOLUME_UP)
                self._bus.emit("mic_action", action="volume_up", value=self._config.volume_step)
            case Gesture.THUMB_DOWN:
                self._volume_return_state = GestureState.IDLE
                self._last_volume_emit_ms = self._now_ms()
                self._set_state(GestureState.VOLUME_DOWN)
                self._bus.emit(
                    "mic_action", action="volume_down", value=self._config.volume_step,
                )

    def _handle_palm_hold(self, gesture: Gesture, now: float) -> None:
        """Handle gestures while in PALM_HOLD state."""
        match gesture:
            case Gesture.OPEN_PALM:
                self._grace_start_ms = None
                # Check if activation delay has passed
                if (
                    self._palm_start_ms is not None
                    and not self._palm_mute_active
                    and (now - self._palm_start_ms) >= self._config.activation_delay_ms
                ):
                    self._palm_mute_active = True
                    self._bus.emit("mic_action", action="mute")
            case Gesture.CLOSED_FIST:
                self._grace_start_ms = None
                self._palm_mute_active = False
                self._palm_start_ms = None
                self._set_state(GestureState.MUTE_LOCKED)
                self._bus.emit("mic_action", action="lock_mute")
            case _:
                # Other gesture — use grace period before releasing palm hold
                self._start_grace()
                if self._grace_expired():
                    if self._palm_mute_active:
                        self._bus.emit("mic_action", action="unmute")
                        self._palm_mute_active = False
                    self._palm_start_ms = None
                    self._set_state(GestureState.IDLE)

    def _handle_mute_locked(self, gesture: Gesture) -> None:
        """Handle gestures while in MUTE_LOCKED state."""
        match gesture:
            case Gesture.CLOSED_FIST:
                self._set_state(GestureState.FIST_PENDING_UNLOCK)
            case Gesture.THUMB_UP:
                self._volume_return_state = GestureState.MUTE_LOCKED
                self._last_volume_emit_ms = self._now_ms()
                self._set_state(GestureState.VOLUME_UP)
                self._bus.emit("mic_action", action="volume_up", value=self._config.volume_step)
            case Gesture.THUMB_DOWN:
                self._volume_return_state = GestureState.MUTE_LOCKED
                self._last_volume_emit_ms = self._now_ms()
                self._set_state(GestureState.VOLUME_DOWN)
                self._bus.emit(
                    "mic_action", action="volume_down", value=self._config.volume_step,
                )

    def _handle_fist_pending_unlock(self, gesture: Gesture) -> None:
        """Handle gestures while in FIST_PENDING_UNLOCK state."""
        if gesture == Gesture.OPEN_PALM:
            self._grace_start_ms = None
            self._set_state(GestureState.IDLE)
            self._bus.emit("mic_action", action="unlock_mute")
        elif gesture == Gesture.CLOSED_FIST:
            self._grace_start_ms = None
        else:
            self._start_grace()
            if self._grace_expired():
                self._set_state(GestureState.MUTE_LOCKED)

    def _handle_volume(self, gesture: Gesture, step: int) -> None:
        """Handle gestures while in a VOLUME state."""
        expected = Gesture.THUMB_UP if step > 0 else Gesture.THUMB_DOWN
        if gesture == expected:
            now = self._now_ms()
            if (now - self._last_volume_emit_ms) >= self._config.volume_repeat_ms:
                self._last_volume_emit_ms = now
                action = "volume_up" if step > 0 else "volume_down"
                self._bus.emit("mic_action", action=action, value=abs(step))
        else:
            self._set_state(self._volume_return_state)
