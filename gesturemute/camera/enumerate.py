"""macOS camera name discovery via system_profiler.

Uses `system_profiler SPCameraDataType -json` to get human-readable camera
names without extra dependencies. Falls back to generic "Camera N" labels
on non-macOS or on error.

NOTE: system_profiler camera ordering is assumed to match AVFoundation
enumeration order (which OpenCV uses on macOS). This is not guaranteed
by Apple and can differ. The probe-and-validate logic in main.py
compensates for ordering mismatches.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_IPHONE_KEYWORDS = ("iphone", "continuity")
_VIRTUAL_KEYWORDS = ("virtual", "obs", "snap", "manycam", "camo", "logi capture")

# All known Apple built-in camera name patterns.
# Apple uses "<Model> Camera" on M-series (e.g. "MacBook Air Camera"),
# "FaceTime HD Camera" on Intel Macs, and "Built-in" on some older models.
_BUILTIN_PATTERNS = (
    "facetime",
    "built-in",
    "macbook",
    "imac",
    "mac pro",
    "mac mini",
    "mac studio",
)

# Module-level cache to avoid repeated system_profiler subprocess calls.
_camera_cache: list[tuple[int, str]] | None = None


def is_iphone_camera(name: str) -> bool:
    """Return True if *name* looks like an iPhone Continuity Camera."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in _IPHONE_KEYWORDS)


def is_builtin_camera(name: str) -> bool:
    """Return True if *name* looks like a built-in Mac camera.

    Matches all known Apple naming conventions: "FaceTime HD Camera" (Intel),
    "MacBook Air Camera", "MacBook Pro Camera", "iMac Camera", etc. (M-series).
    Excludes iPhone Continuity Cameras and virtual/third-party cameras.
    """
    name_lower = name.lower()
    if any(kw in name_lower for kw in _IPHONE_KEYWORDS):
        return False
    if any(kw in name_lower for kw in _VIRTUAL_KEYWORDS):
        return False
    return any(kw in name_lower for kw in _BUILTIN_PATTERNS)


def list_camera_names(exclude_iphone: bool = False) -> list[tuple[int, str]]:
    """Return a list of (index, human-readable name) for connected cameras.

    On macOS, queries system_profiler for camera device names.
    On other platforms or on error, returns an empty list.

    Results are cached for the lifetime of the process to avoid repeated
    subprocess calls.
    """
    global _camera_cache

    if sys.platform != "darwin":
        return []

    if _camera_cache is None:
        try:
            result = subprocess.run(
                ["system_profiler", "SPCameraDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            data = json.loads(result.stdout)
            cameras = data.get("SPCameraDataType", [])
            _camera_cache = [
                (i, cam.get("_name", f"Camera {i}")) for i, cam in enumerate(cameras)
            ]
            logger.info("Cameras found: %s", _camera_cache)
        except Exception as e:
            logger.debug("Failed to enumerate cameras via system_profiler: %s", e)
            _camera_cache = []

    if exclude_iphone:
        return [(i, n) for i, n in _camera_cache if not is_iphone_camera(n)]
    return list(_camera_cache)


def invalidate_cache() -> None:
    """Clear the camera cache so the next call re-queries system_profiler."""
    global _camera_cache
    _camera_cache = None


def get_camera_name(index: int) -> str:
    """Return the human-readable name for a camera at the given index.

    Returns "Camera N" if the name cannot be determined.
    """
    for i, name in list_camera_names():
        if i == index:
            return name
    return f"Camera {index}"


def find_builtin_camera_index() -> int | None:
    """Find the index of the built-in camera on macOS.

    Matches all known Apple camera names: FaceTime, MacBook Air/Pro Camera,
    iMac Camera, etc. Returns None if no built-in camera is found.
    """
    for index, name in list_camera_names():
        if is_builtin_camera(name):
            return index
    return None


def find_first_non_iphone_index() -> int | None:
    """Return the index of the first camera that is not an iPhone.

    Returns None if no non-iPhone camera is found or not on macOS.
    """
    for index, name in list_camera_names():
        if not is_iphone_camera(name):
            return index
    return None
