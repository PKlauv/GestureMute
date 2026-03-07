"""Gesture, mic state, and gesture state enums."""

from enum import Enum, auto


class Gesture(Enum):
    """Recognized hand gestures from MediaPipe."""

    NONE = auto()
    OPEN_PALM = auto()
    CLOSED_FIST = auto()
    THUMB_UP = auto()
    THUMB_DOWN = auto()

    @classmethod
    def from_label(cls, label: str) -> "Gesture":
        """Convert a MediaPipe gesture label string to a Gesture enum.

        Args:
            label: MediaPipe gesture category name (e.g. "Open_Palm", "Closed_Fist").

        Returns:
            Corresponding Gesture enum value, or Gesture.NONE if unrecognized.
        """
        mapping = {
            "Open_Palm": cls.OPEN_PALM,
            "Closed_Fist": cls.CLOSED_FIST,
            "Thumb_Up": cls.THUMB_UP,
            "Thumb_Down": cls.THUMB_DOWN,
            "None": cls.NONE,
        }
        return mapping.get(label, cls.NONE)


class MicState(Enum):
    """Current microphone state."""

    LIVE = auto()
    MUTED = auto()
    LOCKED_MUTE = auto()


class GestureState(Enum):
    """State machine states for gesture processing."""

    IDLE = auto()
    PALM_HOLD = auto()
    MUTE_LOCKED = auto()
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
