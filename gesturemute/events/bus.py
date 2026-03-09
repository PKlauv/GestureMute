"""Thread-safe synchronous pub/sub event bus."""

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Thread-safe synchronous event emitter for inter-module communication.

    Events used in GestureMute:
        gesture_detected: A gesture was recognized (gesture, confidence).
        no_hand: No hand detected in frame.
        state_changed: Gesture state machine transitioned (old_state, new_state).
        mic_action: Mic control action needed (action, value).
        error: An error occurred (source, message).
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Register a callback for an event.

        Args:
            event: Event name to listen for.
            callback: Function to call when event is emitted.
        """
        with self._lock:
            if callback not in self._listeners[event]:
                self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Remove a callback from an event.

        Args:
            event: Event name to stop listening for.
            callback: Function to remove.
        """
        with self._lock:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event, calling all registered callbacks.

        Args:
            event: Event name to emit.
            **kwargs: Data passed to each callback.
        """
        with self._lock:
            callbacks = list(self._listeners.get(event, []))
        for callback in callbacks:
            try:
                callback(**kwargs)
            except Exception:
                logger.exception("Error in listener for event '%s'", event)
