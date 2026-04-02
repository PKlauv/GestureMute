"""Tests for menu bar icon generation."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from gesturemute.gesture.gestures import MicState


@pytest.fixture(autouse=True)
def _ensure_qapp():
    """Ensure a QApplication exists for icon rendering."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield


class TestGenerateTrayIcon:
    """Tests for generate_tray_icon()."""

    @pytest.mark.parametrize("state", [
        MicState.LIVE,
        MicState.MUTED,
        MicState.LOCKED_MUTE,
        None,
    ])
    def test_returns_valid_qicon(self, state):
        from gesturemute.ui.icons import generate_tray_icon
        icon = generate_tray_icon(state)
        assert not icon.isNull()

    @pytest.mark.parametrize("state", [
        MicState.LIVE,
        MicState.MUTED,
        MicState.LOCKED_MUTE,
        None,
    ])
    def test_icon_has_available_sizes(self, state):
        from gesturemute.ui.icons import generate_tray_icon
        icon = generate_tray_icon(state)
        sizes = icon.availableSizes()
        assert len(sizes) > 0

    def test_light_and_dark_produce_different_icons(self):
        from PyQt6.QtCore import Qt
        from gesturemute.ui.icons import generate_tray_icon

        with patch("gesturemute.ui.icons._is_dark_mode", return_value=False):
            light_icon = generate_tray_icon(MicState.LIVE)
        with patch("gesturemute.ui.icons._is_dark_mode", return_value=True):
            dark_icon = generate_tray_icon(MicState.LIVE)

        # Convert to pixmaps and compare — they should differ
        light_img = light_icon.pixmap(32, 32).toImage()
        dark_img = dark_icon.pixmap(32, 32).toImage()
        assert light_img != dark_img

    def test_different_states_produce_different_icons(self):
        from gesturemute.ui.icons import generate_tray_icon

        live = generate_tray_icon(MicState.LIVE).pixmap(32, 32).toImage()
        muted = generate_tray_icon(MicState.MUTED).pixmap(32, 32).toImage()
        locked = generate_tray_icon(MicState.LOCKED_MUTE).pixmap(32, 32).toImage()
        paused = generate_tray_icon(None).pixmap(32, 32).toImage()

        icons = [live, muted, locked, paused]
        # Each state should produce a visually distinct icon
        for i in range(len(icons)):
            for j in range(i + 1, len(icons)):
                assert icons[i] != icons[j], f"States {i} and {j} produced identical icons"
