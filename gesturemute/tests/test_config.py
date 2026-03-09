"""Tests for configuration loading and persistence."""

import json
from pathlib import Path

import pytest

from gesturemute.config import Config


@pytest.fixture
def tmp_config(tmp_path):
    """Return a path to a temporary config file."""
    return tmp_path / "config.json"


class TestDefaults:
    def test_default_values(self):
        config = Config()
        assert config.camera_index == 0
        assert config.confidence_threshold == 0.7
        assert config.gesture_cooldown_ms == 500
        assert config.activation_delay_ms == 300
        assert config.no_hand_timeout_ms == 3000
        assert config.volume_step == 3
        assert config.frame_skip == 1
        assert config.model_path == "models/gesture_recognizer.task"


class TestJsonRoundtrip:
    def test_save_and_load(self, tmp_config):
        original = Config(camera_index=1, confidence_threshold=0.8, volume_step=10)
        original.to_json(tmp_config)

        loaded = Config.from_json(tmp_config)
        assert loaded.camera_index == 1
        assert loaded.confidence_threshold == 0.8
        assert loaded.volume_step == 10
        # Defaults preserved for unmodified fields
        assert loaded.gesture_cooldown_ms == 500


class TestMissingFile:
    def test_missing_file_returns_defaults(self, tmp_path):
        config = Config.from_json(tmp_path / "nonexistent.json")
        assert config.camera_index == 0
        assert config.confidence_threshold == 0.7


class TestConfidenceThresholds:
    def test_default_thresholds(self):
        config = Config()
        assert config.confidence_thresholds == {
            "Open_Palm": 0.5,
            "Closed_Fist": 0.7,
            "Thumb_Up": 0.55,
            "Thumb_Down": 0.7,
            "Two_Fists_Close": 0.7,
        }

    def test_thresholds_roundtrip(self, tmp_config):
        original = Config(confidence_thresholds={"Open_Palm": 0.4, "Thumb_Up": 0.6})
        original.to_json(tmp_config)

        loaded = Config.from_json(tmp_config)
        assert loaded.confidence_thresholds == {"Open_Palm": 0.4, "Thumb_Up": 0.6}

    def test_partial_config_without_thresholds_gets_defaults(self, tmp_config):
        tmp_config.write_text(json.dumps({"camera_index": 2}))
        config = Config.from_json(tmp_config)
        assert config.confidence_thresholds == {
            "Open_Palm": 0.5,
            "Closed_Fist": 0.7,
            "Thumb_Up": 0.55,
            "Thumb_Down": 0.7,
            "Two_Fists_Close": 0.7,
        }


class TestPartialJson:
    def test_partial_json_merges_with_defaults(self, tmp_config):
        tmp_config.write_text(json.dumps({"camera_index": 2, "volume_step": 3}))

        config = Config.from_json(tmp_config)
        assert config.camera_index == 2
        assert config.volume_step == 3
        # All other fields should be defaults
        assert config.confidence_threshold == 0.7
        assert config.gesture_cooldown_ms == 500
        assert config.model_path == "models/gesture_recognizer.task"
