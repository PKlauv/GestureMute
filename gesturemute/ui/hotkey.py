"""Global hotkey listener for Windows (Ctrl+Shift+G)."""

import ctypes
import ctypes.wintypes
import logging
import sys

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_HOTKEY_ID = 1
_MOD_CTRL = 0x0002
_MOD_SHIFT = 0x0004
_VK_G = 0x47
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012


class GlobalHotkey(QThread):
    """Listens for Ctrl+Shift+G via the Windows RegisterHotKey API.

    Signals:
        triggered: Emitted when the hotkey is pressed.
    """

    triggered = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._thread_id: int | None = None

    def run(self) -> None:
        """Register hotkey and enter message loop."""
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, _HOTKEY_ID, _MOD_CTRL | _MOD_SHIFT, _VK_G):
            logger.warning("Failed to register global hotkey Ctrl+Shift+G")
            return

        logger.info("Global hotkey Ctrl+Shift+G registered")
        msg = ctypes.wintypes.MSG()

        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self.triggered.emit()

        user32.UnregisterHotKey(None, _HOTKEY_ID)
        logger.info("Global hotkey unregistered")

    def stop(self) -> None:
        """Unblock the message loop and wait for thread exit."""
        if self._thread_id is not None and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        self.wait()
