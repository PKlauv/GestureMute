"""Application configuration with JSON persistence."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config.json")


@dataclass
class Config:
    """Application settings with defaults matching CLAUDE.md design tokens.

    Attributes:
        camera_index: OpenCV camera device index.
        confidence_threshold: Minimum gesture confidence (0.5-0.95).
        gesture_cooldown_ms: Milliseconds between state transitions.
        activation_delay_ms: Milliseconds before palm activates mute.
        no_hand_timeout_ms: Milliseconds before returning to idle.
        transition_grace_ms: Grace period (ms) before dropping state on bad input.
        volume_step: Percent volume change per gesture cycle.
        frame_skip: Process every Nth frame.
        toast_duration_ms: Milliseconds to show toast notifications.
        model_path: Path to MediaPipe gesture recognizer model.
    """

    camera_index: int = 0
    confidence_threshold: float = 0.7
    confidence_thresholds: dict[str, float] = field(default_factory=lambda: {
        "Open_Palm": 0.5,
        "Closed_Fist": 0.7,
        "Thumb_Up": 0.55,
        "Thumb_Down": 0.7,
    })
    gesture_cooldown_ms: int = 500
    activation_delay_ms: int = 300
    no_hand_timeout_ms: int = 3000
    transition_grace_ms: int = 400
    volume_step: int = 3
    frame_skip: int = 2
    model_path: str = "models/gesture_recognizer.task"
    toast_duration_ms: int = 1500
    camera_backend: str = "auto"
    overlay_style: str = "dot"
    onboarding_completed: bool = False

    def to_json(self, path: Path | None = None) -> None:
        """Save configuration to a JSON file.

        Args:
            path: File path to write. Defaults to CONFIG_PATH.
        """
        path = path or CONFIG_PATH
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: Path | None = None) -> "Config":
        """Load configuration from a JSON file, falling back to defaults.

        Missing keys use default values. If the file doesn't exist or is
        invalid JSON, returns a Config with all defaults.

        Args:
            path: File path to read. Defaults to CONFIG_PATH.

        Returns:
            Config instance with values from file merged with defaults.
        """
        path = path or CONFIG_PATH
        if not path.exists():
            logger.info("Config file not found at %s, using defaults", path)
            return cls()
        try:
            data = json.loads(path.read_text())
            # Only use keys that are valid Config fields
            valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return cls(**filtered)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse config at %s: %s. Using defaults.", path, e)
            return cls()
