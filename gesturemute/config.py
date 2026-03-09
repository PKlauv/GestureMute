"""Application configuration with JSON persistence."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config.json")

# Current config schema version
CONFIG_VERSION = 1


def _clamp(value: int | float, lo: int | float, hi: int | float) -> int | float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


@dataclass
class Config:
    """Application settings with defaults matching CLAUDE.md design tokens.

    Attributes:
        config_version: Schema version for forward compatibility.
        camera_index: OpenCV camera device index (0-9).
        confidence_threshold: Minimum gesture confidence (0.1-1.0).
        gesture_cooldown_ms: Milliseconds between state transitions (100-5000).
        activation_delay_ms: Milliseconds before palm activates mute (50-2000).
        no_hand_timeout_ms: Milliseconds before returning to idle.
        transition_grace_ms: Grace period (ms) before dropping state on bad input.
        volume_step: Percent volume change per gesture cycle (1-20).
        frame_skip: Process every Nth frame (1-10).
        toast_duration_ms: Milliseconds to show toast notifications (500-5000).
        model_path: Path to MediaPipe gesture recognizer model.
    """

    config_version: int = CONFIG_VERSION
    camera_index: int = 0
    confidence_threshold: float = 0.7
    confidence_thresholds: dict[str, float] = field(default_factory=lambda: {
        "Open_Palm": 0.5,
        "Closed_Fist": 0.7,
        "Thumb_Up": 0.55,
        "Thumb_Down": 0.7,
        "Two_Fists_Close": 0.7,
    })
    gesture_cooldown_ms: int = 500
    activation_delay_ms: int = 300
    no_hand_timeout_ms: int = 3000
    transition_grace_ms: int = 400
    volume_step: int = 3
    frame_skip: int = 1
    model_path: str = "models/gesture_recognizer.task"
    toast_duration_ms: int = 1500
    camera_backend: str = "auto"
    overlay_style: str = "pill"
    overlay_x: int | None = None
    overlay_y: int | None = None
    two_fists_max_distance: float = 0.35
    onboarding_completed: bool = False
    sound_cues_enabled: bool = True

    def __post_init__(self) -> None:
        """Validate and clamp all fields to safe ranges."""
        self.camera_index = int(_clamp(self.camera_index, 0, 9))
        self.frame_skip = int(_clamp(self.frame_skip, 1, 10))
        self.gesture_cooldown_ms = int(_clamp(self.gesture_cooldown_ms, 100, 5000))
        self.activation_delay_ms = int(_clamp(self.activation_delay_ms, 50, 2000))
        self.confidence_threshold = float(_clamp(self.confidence_threshold, 0.1, 1.0))
        self.volume_step = int(_clamp(self.volume_step, 1, 20))
        self.toast_duration_ms = int(_clamp(self.toast_duration_ms, 500, 5000))
        self.confidence_thresholds = {
            k: float(_clamp(v, 0.1, 1.0))
            for k, v in self.confidence_thresholds.items()
        }
        self.two_fists_max_distance = float(_clamp(self.two_fists_max_distance, 0.1, 1.0))

    def to_json(self, path: Path | None = None) -> None:
        """Save configuration to a JSON file atomically.

        Writes to a temp file first, then replaces the target to prevent
        corruption if the app crashes mid-write.

        Args:
            path: File path to write. Defaults to CONFIG_PATH.
        """
        path = path or CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(asdict(self), indent=2)
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp", prefix=".config_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                f.write(data)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
            version = filtered.pop("config_version", 1)
            if version > CONFIG_VERSION:
                logger.warning(
                    "Config version %d is newer than supported %d, some fields may be ignored",
                    version, CONFIG_VERSION,
                )
            return cls(config_version=CONFIG_VERSION, **filtered)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse config at %s: %s. Using defaults.", path, e)
            return cls()
