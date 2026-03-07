"""Tests for the gesture state machine."""

import time
from unittest.mock import patch

import pytest

from gesturemute.config import Config
from gesturemute.events.bus import EventBus
from gesturemute.gesture.gestures import Gesture, GestureState
from gesturemute.gesture.state_machine import GestureStateMachine


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def config():
    return Config(
        gesture_cooldown_ms=500,
        activation_delay_ms=300,
        confidence_threshold=0.7,
    )


@pytest.fixture
def sm(bus, config):
    return GestureStateMachine(bus, config)


def _collect_actions(bus: EventBus) -> list[dict]:
    """Subscribe to mic_action and collect all emitted actions."""
    actions = []
    bus.subscribe("mic_action", lambda **kw: actions.append(kw))
    return actions


class TestInitialState:
    def test_starts_idle(self, sm):
        assert sm.state == GestureState.IDLE


class TestPalmMute:
    def test_palm_enters_palm_hold(self, sm):
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

    def test_palm_held_past_delay_emits_mute(self, sm, bus):
        actions = _collect_actions(bus)

        # First detection: enters PALM_HOLD, starts timer
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD
        assert len(actions) == 0  # No mute yet

        # Simulate time passing beyond activation delay
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 350,
        ):
            sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        assert any(a["action"] == "mute" for a in actions)

    def test_palm_released_before_delay_no_mute(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        # Release before 300ms activation delay
        sm.on_no_hand()

        assert sm.state == GestureState.IDLE
        assert not any(a["action"] == "mute" for a in actions)

    def test_no_hand_from_palm_hold_unmutes_if_active(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        # Activate mute
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 350,
        ):
            sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        # Now release hand
        sm.on_no_hand()

        assert sm.state == GestureState.IDLE
        action_names = [a["action"] for a in actions]
        assert "mute" in action_names
        assert "unmute" in action_names


class TestMuteLock:
    def test_palm_to_fist_locks_mute(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        # Need cooldown to pass for fist transition
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 600,
        ):
            sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        assert sm.state == GestureState.MUTE_LOCKED
        assert any(a["action"] == "lock_mute" for a in actions)

    def test_fist_to_palm_unlocks_mute(self, sm, bus):
        actions = _collect_actions(bus)

        # Get to MUTE_LOCKED
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 600,
        ):
            sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Unlock with palm
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 1200,
        ):
            sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "unlock_mute" for a in actions)

    def test_no_hand_from_locked_stays_locked(self, sm, bus):
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 600,
        ):
            sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        sm.on_no_hand()
        assert sm.state == GestureState.MUTE_LOCKED


class TestCooldown:
    def test_rapid_transition_ignored(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)

        # Try fist immediately (before cooldown)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        # Cooldown blocks the fist transition, state stays PALM_HOLD
        assert sm.state == GestureState.PALM_HOLD
        assert not any(a["action"] == "lock_mute" for a in actions)


class TestLowConfidence:
    def test_low_confidence_ignored(self, sm):
        sm.on_gesture(Gesture.OPEN_PALM, 0.3)
        assert sm.state == GestureState.IDLE


class TestVolume:
    def test_thumb_up_volume(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.THUMB_UP, 0.9)

        assert sm.state == GestureState.VOLUME_UP
        assert any(a["action"] == "volume_up" for a in actions)

    def test_thumb_down_volume(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.THUMB_DOWN, 0.9)

        assert sm.state == GestureState.VOLUME_DOWN
        assert any(a["action"] == "volume_down" for a in actions)

    def test_volume_release_returns_idle(self, sm, bus):
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP

        sm.on_no_hand()
        assert sm.state == GestureState.IDLE
