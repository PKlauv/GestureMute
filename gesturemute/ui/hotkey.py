"""Global hotkey listener (Ctrl+Shift+G) for Windows and macOS."""

import logging
import sys

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class _WindowsGlobalHotkey(QThread):
    """Listens for Ctrl+Shift+G via the Windows RegisterHotKey API.

    Signals:
        triggered: Emitted when the hotkey is pressed.
    """

    triggered = pyqtSignal()

    _HOTKEY_ID = 1
    _MOD_CTRL = 0x0002
    _MOD_SHIFT = 0x0004
    _VK_G = 0x47
    _WM_HOTKEY = 0x0312
    _WM_QUIT = 0x0012

    def __init__(self) -> None:
        super().__init__()
        self._thread_id: int | None = None

    def run(self) -> None:
        """Register hotkey and enter message loop."""
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(
            None, self._HOTKEY_ID, self._MOD_CTRL | self._MOD_SHIFT, self._VK_G
        ):
            logger.warning("Failed to register global hotkey Ctrl+Shift+G")
            return

        logger.info("Global hotkey Ctrl+Shift+G registered (Windows)")
        msg = ctypes.wintypes.MSG()

        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self._WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                self.triggered.emit()

        user32.UnregisterHotKey(None, self._HOTKEY_ID)
        logger.info("Global hotkey unregistered (Windows)")

    def stop(self) -> None:
        """Unblock the message loop and wait for thread exit."""
        if self._thread_id is not None:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, self._WM_QUIT, 0, 0
            )
        self.wait()


class _MacGlobalHotkey(QThread):
    """Listens for Ctrl+Shift+G via macOS Quartz Event Taps.

    Requires Accessibility permissions (System Settings > Privacy & Security
    > Accessibility). If permissions are not granted, the event tap will fail
    to create and a warning will be logged.

    Signals:
        triggered: Emitted when the hotkey is pressed.
    """

    triggered = pyqtSignal()
    failed = pyqtSignal(str)

    def run(self) -> None:
        """Create an event tap and enter the CFRunLoop."""
        try:
            from Quartz import (
                CFMachPortCreateRunLoopSource,
                CFRunLoopAddSource,
                CFRunLoopGetCurrent,
                CFRunLoopRun,
                CGEventGetFlags,
                CGEventGetIntegerValueField,
                CGEventTapCreate,
                CGEventTapEnable,
                kCFRunLoopCommonModes,
                kCGEventFlagMaskControl,
                kCGEventFlagMaskShift,
                kCGEventKeyDown,
                kCGHeadInsertEventTap,
                kCGKeyboardEventKeycode,
                kCGSessionEventTap,
            )
        except ImportError:
            logger.warning(
                "pyobjc-framework-Quartz not installed — global hotkey disabled. "
                "Install with: pip install pyobjc-framework-Quartz"
            )
            self.failed.emit(
                "Global hotkey disabled — install pyobjc-framework-Quartz"
            )
            return

        _VK_G_MAC = 5  # macOS virtual keycode for 'G'

        def callback(proxy, event_type, event, refcon):
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            flags = CGEventGetFlags(event)
            ctrl = bool(flags & kCGEventFlagMaskControl)
            shift = bool(flags & kCGEventFlagMaskShift)
            if keycode == _VK_G_MAC and ctrl and shift:
                self.triggered.emit()
            return event

        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            0,
            1 << kCGEventKeyDown,
            callback,
            None,
        )
        if tap is None:
            logger.warning(
                "Failed to create event tap — grant Accessibility permission "
                "(System Settings > Privacy & Security > Accessibility)"
            )
            self.failed.emit(
                "Global hotkey requires Accessibility permission.\n"
                "Grant it in: System Settings \u2192 Privacy & Security \u2192 Accessibility"
            )
            return

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        self._run_loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._run_loop, source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)
        logger.info("Global hotkey Ctrl+Shift+G registered (macOS)")
        CFRunLoopRun()
        logger.info("Global hotkey unregistered (macOS)")

    def stop(self) -> None:
        """Stop the CFRunLoop and wait for thread exit."""
        if hasattr(self, "_run_loop") and self._run_loop:
            from Quartz import CFRunLoopStop

            CFRunLoopStop(self._run_loop)
        self.wait()


def create_global_hotkey() -> QThread | None:
    """Return a platform-appropriate global hotkey listener, or None."""
    if sys.platform == "win32":
        return _WindowsGlobalHotkey()
    elif sys.platform == "darwin":
        return _MacGlobalHotkey()
    return None
