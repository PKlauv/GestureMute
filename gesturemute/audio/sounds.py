"""Sound cue playback for mic state changes."""

import logging
import math
import struct
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

_SOUNDS_DIR = Path(__file__).parent / "sounds"

# Action -> WAV filename mapping
_ACTION_MAP = {
    "mute": "mute.wav",
    "unmute": "unmute.wav",
    "lock_mute": "lock.wav",
    "unlock_mute": "unmute.wav",
}

# Try importing QSoundEffect from PyQt6 multimedia
try:
    from PyQt6.QtMultimedia import QSoundEffect
    from PyQt6.QtCore import QUrl
    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False
    logger.debug("PyQt6-Multimedia not available, sound cues disabled")


def generate_wav_files() -> None:
    """Generate simple sine-burst WAV files for sound cues.

    Creates ~50ms sine wave tones at different frequencies:
    - mute.wav: 440 Hz descending
    - unmute.wav: 880 Hz ascending
    - lock.wav: 330 Hz double pulse
    """
    _SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

    sample_rate = 22050
    duration_ms = 50
    num_samples = int(sample_rate * duration_ms / 1000)

    def _write_wav(filename: str, freq: float, volume: float = 0.3) -> None:
        path = _SOUNDS_DIR / filename
        if path.exists():
            return
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            # Apply fade-in/out envelope to avoid clicks
            envelope = 1.0
            fade = int(num_samples * 0.1)
            if i < fade:
                envelope = i / fade
            elif i > num_samples - fade:
                envelope = (num_samples - i) / fade
            val = volume * envelope * math.sin(2 * math.pi * freq * t)
            samples.append(int(val * 32767))

        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    _write_wav("mute.wav", 440)
    _write_wav("unmute.wav", 880)
    _write_wav("lock.wav", 330)


class SoundCuePlayer:
    """Plays short WAV sound cues on mic state changes.

    Uses QSoundEffect for low-latency playback on the Qt event loop.
    Falls back to a no-op if PyQt6-Multimedia is not installed.

    Args:
        enabled: Whether sound cues are initially enabled.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and _HAS_MULTIMEDIA
        self._effects: dict[str, "QSoundEffect"] = {}

        if not _HAS_MULTIMEDIA:
            return

        generate_wav_files()

        for action, filename in _ACTION_MAP.items():
            path = _SOUNDS_DIR / filename
            if path.exists():
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(0.5)
                self._effects[action] = effect

    @staticmethod
    def is_available() -> bool:
        """Return True if multimedia backend is available."""
        return _HAS_MULTIMEDIA

    def play(self, action: str) -> None:
        """Play the sound cue for the given action.

        Args:
            action: One of "mute", "unmute", "lock_mute", "unlock_mute".
        """
        if not self._enabled:
            return
        effect = self._effects.get(action)
        if effect is not None:
            effect.play()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sound cue playback.

        Args:
            enabled: Whether to play sound cues.
        """
        self._enabled = enabled and _HAS_MULTIMEDIA
