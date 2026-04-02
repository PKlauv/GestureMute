"""Lightweight signal/slot replacement for pyqtSignal.

Drop-in replacement that preserves the .connect()/.emit()/.disconnect() API
so worker classes can be used without PyQt6.
"""

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Signal:
    """Thread-safe signal that calls connected callbacks synchronously.

    Unlike pyqtSignal, callbacks run on the emitter's thread (no Qt event
    loop required). This is fine for the bridge subprocess where there is
    no main-thread GUI constraint.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Any]] = []
        self._lock = threading.Lock()

    def connect(self, callback: Callable[..., Any]) -> None:
        """Register a callback."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any] | None = None) -> None:
        """Remove a callback, or all callbacks if None."""
        with self._lock:
            if callback is None:
                self._callbacks.clear()
            else:
                try:
                    self._callbacks.remove(callback)
                except ValueError:
                    pass

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """Call all connected callbacks with the given arguments."""
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                logger.exception("Error in signal callback")
