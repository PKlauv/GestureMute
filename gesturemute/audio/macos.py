"""macOS microphone control via osascript."""

import logging
import subprocess

from gesturemute.audio.controller import AudioController

logger = logging.getLogger(__name__)


def _osascript(script: str) -> str:
    """Run an AppleScript command and return stdout.

    Args:
        script: AppleScript code to execute.

    Returns:
        Stripped stdout output from osascript.
    """
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"osascript failed: {result.stderr.strip()}")
    return result.stdout.strip()


class MacOSAudioController(AudioController):
    """Controls the default microphone on macOS using osascript."""

    def __init__(self) -> None:
        logger.info("macOS audio controller initialized")

    def mute(self) -> None:
        """Mute the system microphone."""
        try:
            _osascript("set volume input volume 0")
            logger.debug("Microphone muted")
        except Exception:
            logger.exception("Failed to mute microphone")

    def unmute(self) -> None:
        """Unmute the system microphone."""
        try:
            _osascript("set volume input volume 100")
            logger.debug("Microphone unmuted")
        except Exception:
            logger.exception("Failed to unmute microphone")

    def toggle_mute(self) -> None:
        """Toggle the system microphone mute state."""
        try:
            if self.is_muted():
                self.unmute()
            else:
                self.mute()
        except Exception:
            logger.exception("Failed to toggle microphone mute")

    def is_muted(self) -> bool:
        """Return True if the system microphone is currently muted."""
        try:
            result = _osascript("input volume of (get volume settings)")
            return int(result) == 0
        except Exception:
            logger.exception("Failed to read microphone mute state")
            return False

    def get_volume(self) -> float:
        """Return the current microphone volume as a float 0.0-1.0."""
        try:
            result = _osascript("input volume of (get volume settings)")
            return int(result) / 100.0
        except Exception:
            logger.exception("Failed to read microphone volume")
            return 0.0

    def set_volume(self, level: float) -> None:
        """Set microphone volume.

        Args:
            level: Volume level from 0.0 to 1.0.
        """
        try:
            clamped = max(0, min(100, int(level * 100)))
            _osascript(f"set volume input volume {clamped}")
            logger.debug("Microphone volume set to %d%%", clamped)
        except Exception:
            logger.exception("Failed to set microphone volume")

    def adjust_volume(self, step: int) -> int:
        """Adjust microphone volume by a percentage step.

        Uses a single osascript call to read, adjust, and return the new level.

        Args:
            step: Positive or negative percentage to adjust (e.g. 5 or -5).

        Returns:
            The new volume level as an integer 0-100.
        """
        try:
            script = (
                f"set curVol to input volume of (get volume settings)\n"
                f"set newVol to curVol + ({int(step)})\n"
                f"if newVol < 0 then set newVol to 0\n"
                f"if newVol > 100 then set newVol to 100\n"
                f"set volume input volume newVol\n"
                f"return newVol"
            )
            result = _osascript(script)
            return int(result)
        except Exception:
            logger.exception("Failed to adjust microphone volume")
            return 0

    def cleanup(self) -> None:
        """No-op on macOS. Safe to call multiple times."""
        logger.info("macOS audio controller cleaned up")
