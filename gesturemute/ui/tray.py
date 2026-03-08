"""System tray icon with context menu for GestureMute."""

import logging

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from gesturemute.gesture.gestures import MicState
from gesturemute.ui.theme import mic_state_color

logger = logging.getLogger(__name__)

_ICON_SIZE = 64


class SystemTray(QObject):
    """System tray icon with context menu.

    Signals:
        toggle_detection_requested: Emitted when user toggles detection.
        quit_requested: Emitted when user selects Quit.
    """

    toggle_detection_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._tray.setToolTip("GestureMute")

        self._menu = QMenu()
        self._toggle_action = QAction("Toggle Detection (Ctrl+Shift+G)")
        self._toggle_action.triggered.connect(self.toggle_detection_requested.emit)
        self._menu.addAction(self._toggle_action)

        self._settings_action = QAction("Settings...")
        self._settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(self._settings_action)

        self._menu.addSeparator()

        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._quit_action)

        self._tray.setContextMenu(self._menu)
        self.update_icon(MicState.LIVE)

    def update_icon(self, mic_state: MicState | None) -> None:
        """Regenerate the tray icon with the appropriate color.

        Args:
            mic_state: Current mic state, or None for paused.
        """
        color_hex = mic_state_color(mic_state)
        self._tray.setIcon(self._generate_icon(color_hex))

    @staticmethod
    def _generate_icon(color_hex: str) -> QIcon:
        """Draw a colored circle icon on a transparent pixmap."""
        pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.setBrush(QColor(color_hex))
        margin = 4
        painter.drawEllipse(margin, margin, _ICON_SIZE - 2 * margin, _ICON_SIZE - 2 * margin)
        painter.end()
        return QIcon(pixmap)

    def show(self) -> None:
        """Show the tray icon and display a startup notification."""
        self._tray.show()
        self._tray.showMessage(
            "GestureMute",
            "Running in system tray. Right-click the tray icon for options.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )
