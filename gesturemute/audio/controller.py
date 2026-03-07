"""Abstract base class for platform audio controllers."""

from abc import ABC, abstractmethod


class AudioController(ABC):
    """Platform-agnostic interface for microphone control.

    Implementations must handle platform-specific initialization (e.g. COM
    on Windows) in __init__ and teardown in cleanup().
    """

    @abstractmethod
    def mute(self) -> None:
        """Mute the system microphone."""

    @abstractmethod
    def unmute(self) -> None:
        """Unmute the system microphone."""

    @abstractmethod
    def toggle_mute(self) -> None:
        """Toggle the system microphone mute state."""

    @abstractmethod
    def is_muted(self) -> bool:
        """Return True if the system microphone is currently muted."""

    @abstractmethod
    def get_volume(self) -> float:
        """Return the current microphone volume as a float 0.0-1.0."""

    @abstractmethod
    def set_volume(self, level: float) -> None:
        """Set microphone volume.

        Args:
            level: Volume level from 0.0 to 1.0.
        """

    @abstractmethod
    def adjust_volume(self, step: int) -> None:
        """Adjust microphone volume by a percentage step.

        Args:
            step: Positive or negative percentage to adjust (e.g. 5 or -5).
        """

    @abstractmethod
    def cleanup(self) -> None:
        """Release platform resources (COM, etc.)."""
