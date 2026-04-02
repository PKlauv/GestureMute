"""System tray icon with context menu for GestureMute."""

import logging

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from gesturemute.gesture.gestures import MicState
from gesturemute.ui.icons import generate_tray_icon

logger = logging.getLogger(__name__)


class SystemTray(QObject):
    """System tray icon with context menu.

    Signals:
        toggle_detection_requested: Emitted when user toggles detection.
        quit_requested: Emitted when user selects Quit.
    """

    toggle_detection_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    preview_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._tray.setToolTip("GestureMute")
        self._current_state: MicState | None = MicState.LIVE

        self._menu = QMenu()

        # Status header (non-clickable)
        self._status_action = QAction("Microphone Live")
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()

        self._toggle_action = QAction("Toggle Detection (Ctrl+Shift+G)")
        self._toggle_action.triggered.connect(self.toggle_detection_requested.emit)
        self._menu.addAction(self._toggle_action)

        self._settings_action = QAction("Settings...")
        self._settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(self._settings_action)

        self._preview_action = QAction("Preview")
        self._preview_action.triggered.connect(self.preview_requested.emit)
        self._menu.addAction(self._preview_action)

        self._menu.addSeparator()

        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._quit_action)

        self._tray.setContextMenu(self._menu)

        # Re-render icon when system appearance changes (light/dark mode).
        hints = QApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_appearance_changed)

        self.update_icon(MicState.LIVE)

    _TOOLTIP_LABELS = {
        MicState.LIVE: "GestureMute - Microphone is live",
        MicState.MUTED: "GestureMute - Microphone is muted",
        MicState.LOCKED_MUTE: "GestureMute - Microphone is mute-locked",
    }

    _STATUS_LABELS = {
        MicState.LIVE: "Microphone Live",
        MicState.MUTED: "Microphone Muted",
        MicState.LOCKED_MUTE: "Mute Locked",
    }

    def update_icon(self, mic_state: MicState | None) -> None:
        """Regenerate the tray icon with the appropriate color and tooltip.

        Args:
            mic_state: Current mic state, or None for paused.
        """
        self._current_state = mic_state
        self._tray.setIcon(generate_tray_icon(mic_state))
        tooltip = self._TOOLTIP_LABELS.get(mic_state, "GestureMute - Detection paused") if mic_state else "GestureMute - Detection paused"
        self._tray.setToolTip(tooltip)
        status = self._STATUS_LABELS.get(mic_state, "Detection Paused") if mic_state else "Detection Paused"
        self._status_action.setText(status)

    def _on_appearance_changed(self) -> None:
        """Re-render the icon when system light/dark mode changes."""
        self.update_icon(self._current_state)

    def show_message(
        self, title: str, message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 3000,
    ) -> None:
        """Display a system tray balloon notification."""
        self._tray.showMessage(title, message, icon, duration_ms)

    def update_toggle_label(self, detection_active: bool) -> None:
        """Update the toggle action text based on detection state."""
        self._toggle_action.setText(
            "Pause Detection (Ctrl+Shift+G)" if detection_active
            else "Resume Detection (Ctrl+Shift+G)"
        )

    def show(self) -> None:
        """Show the tray icon and display a startup notification."""
        self._tray.show()
        self.show_message(
            "GestureMute",
            "Running in system tray. Right-click the tray icon for options.",
        )
