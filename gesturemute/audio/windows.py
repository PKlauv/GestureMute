"""Windows microphone control via pycaw/comtypes."""

import logging

import comtypes
from ctypes import POINTER, cast
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

from gesturemute.audio.controller import AudioController

logger = logging.getLogger(__name__)


class WindowsAudioController(AudioController):
    """Controls the default microphone on Windows using pycaw.

    Requires comtypes COM initialization. Call cleanup() when done.
    """

    def __init__(self) -> None:
        comtypes.CoInitialize()
        mic = AudioUtilities.GetMicrophone()
        if mic is None:
            raise RuntimeError("No microphone found. Check audio device settings.")
        interface = mic.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        self._volume = cast(interface, POINTER(IAudioEndpointVolume))
        logger.info("Windows audio controller initialized")

    def mute(self) -> None:
        """Mute the system microphone."""
        self._volume.SetMute(True, None)
        logger.debug("Microphone muted")

    def unmute(self) -> None:
        """Unmute the system microphone."""
        self._volume.SetMute(False, None)
        logger.debug("Microphone unmuted")

    def toggle_mute(self) -> None:
        """Toggle the system microphone mute state."""
        current = self.is_muted()
        self._volume.SetMute(not current, None)
        logger.debug("Microphone mute toggled to %s", not current)

    def is_muted(self) -> bool:
        """Return True if the system microphone is currently muted."""
        return bool(self._volume.GetMute())

    def get_volume(self) -> float:
        """Return the current microphone volume as a float 0.0-1.0."""
        return self._volume.GetMasterVolumeLevelScalar()

    def set_volume(self, level: float) -> None:
        """Set microphone volume.

        Args:
            level: Volume level from 0.0 to 1.0.
        """
        clamped = max(0.0, min(1.0, level))
        self._volume.SetMasterVolumeLevelScalar(clamped, None)
        logger.debug("Microphone volume set to %.0f%%", clamped * 100)

    def adjust_volume(self, step: int) -> None:
        """Adjust microphone volume by a percentage step.

        Args:
            step: Positive or negative percentage to adjust (e.g. 5 or -5).
        """
        current = self.get_volume()
        new_level = current + (step / 100.0)
        self.set_volume(new_level)

    def cleanup(self) -> None:
        """Release COM resources."""
        comtypes.CoUninitialize()
        logger.info("Windows audio controller cleaned up")
