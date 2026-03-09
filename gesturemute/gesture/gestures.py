"""Gesture, mic state, and gesture state enums."""

from dataclasses import dataclass, field
from enum import Enum, auto


class Gesture(Enum):
    """Recognized hand gestures from MediaPipe."""

    NONE = auto()
    OPEN_PALM = auto()
    CLOSED_FIST = auto()
    THUMB_UP = auto()
    THUMB_DOWN = auto()
    TWO_FISTS_CLOSE = auto()

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

    def to_label(self) -> str:
        """Convert a Gesture enum value to its MediaPipe label string.

        Returns:
            MediaPipe gesture category name (e.g. "Open_Palm"), or "None" for NONE.
        """
        reverse_mapping = {
            self.OPEN_PALM: "Open_Palm",
            self.CLOSED_FIST: "Closed_Fist",
            self.THUMB_UP: "Thumb_Up",
            self.THUMB_DOWN: "Thumb_Down",
            self.TWO_FISTS_CLOSE: "Two_Fists_Close",
            self.NONE: "None",
        }
        return reverse_mapping.get(self, "None")


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
    FIST_PENDING_UNLOCK = auto()
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()


@dataclass
class GestureScores:
    """All gesture confidence scores from a single recognition frame.

    Attributes:
        scores: Mapping of gesture label to confidence (e.g. {"Open_Palm": 0.83}).
        top_gesture: The highest-confidence Gesture enum value.
        top_confidence: Confidence of the top gesture (0-1).
    """

    scores: dict[str, float] = field(default_factory=dict)
    top_gesture: Gesture = Gesture.NONE
    top_confidence: float = 0.0


@dataclass
class HandLandmarks:
    """21 hand landmark points from MediaPipe.

    Attributes:
        points: List of 21 (x, y, z) tuples, normalized 0-1.
        handedness: "Left" or "Right".
    """

    points: list[tuple[float, float, float]] = field(default_factory=list)
    handedness: str = "Unknown"


HAND_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4),           # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # index
    (0, 9), (9, 10), (10, 11), (11, 12),      # middle
    (0, 13), (13, 14), (14, 15), (15, 16),    # ring
    (0, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (5, 9), (9, 13), (13, 17),                 # palm
]
