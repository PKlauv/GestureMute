"""Tests for toast notification system."""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from gesturemute.config import Config
from gesturemute.gesture.gestures import MicState
from gesturemute.ui.toast import ToastManager, ToastNotification, _ACTION_TEXT


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication exists for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_overlay():
    """Return a mock StatusOverlay with position methods."""
    overlay = MagicMock()
    overlay.pos.return_value = QPoint(500, 500)
    overlay.width.return_value = 48
    return overlay


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def manager(qapp, mock_overlay, config):
    return ToastManager(mock_overlay, config)


class TestActionDisplayText:
    def test_all_actions_have_display_text(self):
        expected = {
            "mute": ("Microphone Muted", "Open palm detected"),
            "unmute": ("Microphone Live", "Hand released"),
            "lock_mute": ("Mute Locked", "Palm to fist"),
            "unlock_mute": ("Mute Unlocked", "Fist to palm"),
            "volume_up": ("Volume Up", "Thumbs up"),
            "volume_down": ("Volume Down", "Thumbs down"),
            "pause_detection": ("Detection Paused", "Two fists detected"),
        }
        assert _ACTION_TEXT == expected

    def test_unknown_action_returns_none(self):
        assert _ACTION_TEXT.get("unknown_action") is None


class TestToastReplacesPrevious:
    def test_showing_new_toast_dismisses_old(self, manager):
        manager.show_toast("mute", MicState.MUTED)
        first_toast = manager._current_toast
        assert first_toast is not None

        manager.show_toast("unmute", MicState.LIVE)
        second_toast = manager._current_toast
        assert second_toast is not first_toast

    def test_unknown_action_does_not_create_toast(self, manager):
        manager.show_toast("nonexistent", MicState.LIVE)
        assert manager._current_toast is None


class TestToastAutoDismiss:
    def test_toast_has_dismiss_timer(self, qapp):
        toast = ToastNotification("Test Title", "Test subtitle", "#10B981", 1500)
        assert toast._dismiss_timer.isSingleShot()
        assert toast._duration_ms == 1500
        toast.deleteLater()

    def test_dismiss_hides_toast(self, qapp):
        toast = ToastNotification("Test Title", "Test subtitle", "#10B981", 1500)
        toast.show()
        assert toast.isVisible()
        toast.dismiss()


class TestToastDurationConfig:
    def test_custom_duration(self, qapp, mock_overlay):
        config = Config(toast_duration_ms=2000)
        mgr = ToastManager(mock_overlay, config)
        mgr.show_toast("mute", MicState.MUTED)
        assert mgr._current_toast._dismiss_timer.interval() == 2000
        mgr._current_toast.dismiss()
