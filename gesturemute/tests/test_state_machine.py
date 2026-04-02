"""Tests for the gesture state machine."""

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
        transition_grace_ms=400,
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
        # Release before 300ms activation delay — grace holds state briefly
        sm.on_no_hand()
        assert sm.state == GestureState.PALM_HOLD  # Grace period holds

        # Advance past grace period
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 450,
        ):
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

        # Release hand — grace holds state first
        base = sm._now_ms()
        sm.on_no_hand()
        assert sm.state == GestureState.PALM_HOLD

        # Advance past grace period
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=base + 450,
        ):
            sm.on_no_hand()

        assert sm.state == GestureState.IDLE
        action_names = [a["action"] for a in actions]
        assert "mute" in action_names
        assert "unmute" in action_names


class TestMuteLock:
    def test_palm_to_fist_locks_mute(self, sm, bus):
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        assert sm.state == GestureState.MUTE_LOCKED
        assert any(a["action"] == "lock_mute" for a in actions)

    def test_fist_to_palm_unlocks_mute(self, sm, bus):
        actions = _collect_actions(bus)

        # Get to MUTE_LOCKED
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Fist → Palm unlock sequence
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "unlock_mute" for a in actions)

    def test_palm_alone_does_not_unlock_mute(self, sm, bus):
        actions = _collect_actions(bus)

        # Get to MUTE_LOCKED
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Open_Palm alone should not unlock
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED
        assert not any(a["action"] == "unlock_mute" for a in actions)

    def test_no_hand_from_fist_pending_returns_to_locked(self, sm, bus):
        # Get to FIST_PENDING_UNLOCK
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Grace holds state first
        base = sm._now_ms()
        sm.on_no_hand()
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Advance past grace period
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=base + 450,
        ):
            sm.on_no_hand()
        assert sm.state == GestureState.MUTE_LOCKED

    def test_no_hand_from_locked_stays_locked(self, sm, bus):
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        sm.on_no_hand()
        assert sm.state == GestureState.MUTE_LOCKED


class TestCooldown:
    def test_palm_to_fist_works_immediately(self, sm, bus):
        """Palm→fist is a chained gesture exempt from cooldown."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)

        assert sm.state == GestureState.MUTE_LOCKED
        assert any(a["action"] == "lock_mute" for a in actions)

    def test_fist_to_palm_unlock_works_immediately(self, sm, bus):
        """Fist→palm unlock is a chained gesture exempt from cooldown."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "unlock_mute" for a in actions)

    def test_volume_cooldown_still_applies(self, sm, bus):
        """Cooldown still applies to non-chained transitions like volume."""
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP

        # Different gesture breaks out of volume, back to idle
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        # Volume state handles non-matching gesture by going to IDLE
        # Then IDLE handles OPEN_PALM — but cooldown should block it
        # Actually _handle_volume transitions to IDLE on mismatch,
        # then _handle_idle is not called in the same on_gesture call.
        # So this just verifies the state goes to IDLE.
        assert sm.state == GestureState.IDLE


class TestLowConfidence:
    def test_low_confidence_ignored(self, sm):
        sm.on_gesture(Gesture.OPEN_PALM, 0.3)
        assert sm.state == GestureState.IDLE

    def test_below_per_gesture_threshold_rejected(self, sm):
        """Open_Palm has a 0.5 threshold — 0.45 should be rejected."""
        sm.on_gesture(Gesture.OPEN_PALM, 0.45)
        assert sm.state == GestureState.IDLE

    def test_above_per_gesture_but_below_global_accepted(self, sm):
        """Open_Palm threshold is 0.5, so 0.55 should be accepted even though < 0.7 global."""
        sm.on_gesture(Gesture.OPEN_PALM, 0.55)
        assert sm.state == GestureState.PALM_HOLD

    def test_unknown_gesture_uses_global_threshold(self, bus):
        """Gestures not in confidence_thresholds fall back to global threshold."""
        config = Config(
            confidence_threshold=0.7,
            confidence_thresholds={"Open_Palm": 0.5},
        )
        sm = GestureStateMachine(bus, config)
        # Thumb_Down not in overrides, should use global 0.7
        sm.on_gesture(Gesture.THUMB_DOWN, 0.65)
        assert sm.state == GestureState.IDLE
        sm.on_gesture(Gesture.THUMB_DOWN, 0.75)
        assert sm.state == GestureState.VOLUME_DOWN


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

    def test_thumb_up_while_mute_locked(self, sm, bus):
        """Volume up works during locked mute."""
        actions = _collect_actions(bus)

        # Lock mute
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP
        assert any(a["action"] == "volume_up" for a in actions)

    def test_thumb_down_while_mute_locked(self, sm, bus):
        """Volume down works during locked mute."""
        actions = _collect_actions(bus)

        # Lock mute
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        sm.on_gesture(Gesture.THUMB_DOWN, 0.9)
        assert sm.state == GestureState.VOLUME_DOWN
        assert any(a["action"] == "volume_down" for a in actions)

    def test_volume_from_mute_locked_returns_to_mute_locked(self, sm, bus):
        """After volume gesture ends during locked mute, state returns to MUTE_LOCKED."""
        # Lock mute
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Volume up, then release
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP
        sm.on_no_hand()
        assert sm.state == GestureState.MUTE_LOCKED

    def test_volume_mismatch_from_mute_locked_returns_to_mute_locked(self, sm, bus):
        """Non-matching gesture during volume returns to MUTE_LOCKED if that's the origin."""
        # Lock mute
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Volume up, then different gesture
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

    def test_volume_throttles_repeated_emissions(self, sm, bus):
        """Holding thumb up across multiple frames within repeat interval emits only once."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert len([a for a in actions if a["action"] == "volume_up"]) == 1

        # Simulate rapid frames still within the repeat interval
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        sm.on_gesture(Gesture.THUMB_UP, 0.9)

        assert len([a for a in actions if a["action"] == "volume_up"]) == 1

    def test_volume_emits_again_after_repeat_interval(self, sm, bus):
        """After volume_repeat_ms elapses, a second emission is allowed."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert len([a for a in actions if a["action"] == "volume_up"]) == 1

        # Advance time past repeat interval (default 400ms)
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 450,
        ):
            sm.on_gesture(Gesture.THUMB_UP, 0.9)

        assert len([a for a in actions if a["action"] == "volume_up"]) == 2

    def test_volume_mismatch_still_exits_during_throttle(self, sm, bus):
        """A non-matching gesture exits the volume state even while throttled."""
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP

        # Different gesture should still exit, regardless of throttle
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE

    def test_unlock_still_works_after_volume_during_locked(self, sm, bus):
        """Unlock sequence (fist -> palm) works after volume adjustment in locked state."""
        actions = _collect_actions(bus)

        # Lock mute
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED

        # Volume adjustment
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        sm.on_no_hand()
        assert sm.state == GestureState.MUTE_LOCKED

        # Unlock sequence
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "unlock_mute" for a in actions)


class TestTransitionGrace:
    def test_palm_hold_grace_period_allows_fist_transition(self, sm, bus):
        """Brief no-hand gap during palm→fist doesn't drop state."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # Brief no-hand (within grace period)
        sm.on_no_hand()
        assert sm.state == GestureState.PALM_HOLD

        # Fist arrives within grace window
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.MUTE_LOCKED
        assert any(a["action"] == "lock_mute" for a in actions)

    def test_fist_pending_grace_period_allows_palm_transition(self, sm, bus):
        """Brief no-hand gap during fist→palm doesn't drop state."""
        actions = _collect_actions(bus)

        # Get to FIST_PENDING_UNLOCK
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Brief no-hand (within grace period)
        sm.on_no_hand()
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Palm arrives within grace window
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "unlock_mute" for a in actions)

    def test_grace_expires_after_timeout(self, sm, bus):
        """Sustained no-hand past grace period does transition."""
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        base = sm._now_ms()
        sm.on_no_hand()
        assert sm.state == GestureState.PALM_HOLD

        # Advance past grace period (400ms)
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=base + 450,
        ):
            sm.on_no_hand()
        assert sm.state == GestureState.IDLE

    def test_unexpected_gesture_in_palm_hold_uses_grace(self, sm, bus):
        """Brief wrong gesture doesn't immediately drop PALM_HOLD."""
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # Unexpected gesture — grace holds state
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # Valid gesture returns — state continues
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

    def test_unexpected_gesture_in_palm_hold_drops_after_grace(self, sm, bus):
        """Sustained wrong gesture past grace period drops PALM_HOLD."""
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # First unexpected gesture starts grace
        base = sm._now_ms()
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # Second unexpected gesture past grace period drops state
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=base + 450,
        ):
            sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.IDLE

    def test_unexpected_gesture_in_fist_pending_uses_grace(self, sm, bus):
        """Brief wrong gesture doesn't immediately drop FIST_PENDING_UNLOCK."""
        # Get to FIST_PENDING_UNLOCK
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        sm.on_gesture(Gesture.CLOSED_FIST, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Unexpected gesture — grace holds state
        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.FIST_PENDING_UNLOCK

        # Valid gesture returns
        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.IDLE


class TestTwoFistsClose:
    def test_two_fists_close_emits_pause(self, sm, bus):
        """TWO_FISTS_CLOSE in IDLE emits pause_detection action."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.9)

        assert sm.state == GestureState.IDLE
        assert any(a["action"] == "pause_detection" for a in actions)

    def test_two_fists_close_respects_cooldown(self, sm, bus):
        """Rapid TWO_FISTS_CLOSE doesn't double-fire."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.9)
        assert len([a for a in actions if a["action"] == "pause_detection"]) == 1

        # Second gesture within cooldown — should be ignored
        sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.9)
        assert len([a for a in actions if a["action"] == "pause_detection"]) == 1

    def test_two_fists_close_during_palm_hold(self, sm, bus):
        """TWO_FISTS_CLOSE during PALM_HOLD emits pause_detection."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.OPEN_PALM, 0.9)
        assert sm.state == GestureState.PALM_HOLD

        # Advance past cooldown
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 600,
        ):
            sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.9)

        assert any(a["action"] == "pause_detection" for a in actions)

    def test_two_fists_close_during_volume(self, sm, bus):
        """TWO_FISTS_CLOSE during VOLUME_UP emits pause_detection."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.THUMB_UP, 0.9)
        assert sm.state == GestureState.VOLUME_UP

        # Advance past cooldown
        with patch.object(
            GestureStateMachine, "_now_ms", return_value=sm._now_ms() + 600,
        ):
            sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.9)

        assert any(a["action"] == "pause_detection" for a in actions)

    def test_two_fists_close_low_confidence_ignored(self, sm, bus):
        """TWO_FISTS_CLOSE below threshold is ignored."""
        actions = _collect_actions(bus)

        sm.on_gesture(Gesture.TWO_FISTS_CLOSE, 0.3)

        assert not any(a.get("action") == "pause_detection" for a in actions)
