"""macOS camera discovery via AVFoundation.

Uses AVFoundation's AVCaptureDevice API to enumerate cameras in the same
order that OpenCV uses (since OpenCV uses AVFoundation on macOS). This
guarantees index alignment between our enumeration and cv2.VideoCapture().

Falls back to system_profiler if AVFoundation is unavailable, and to
generic "Camera N" labels on non-macOS or on error.
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

# Module-level cache: list of (index, name, unique_id, model_id)
_camera_cache: list[tuple[int, str, str, str]] | None = None


def is_iphone_camera(name: str, model_id: str = "") -> bool:
    """Return True if the camera is an iPhone Continuity Camera.

    Checks both the display name and the model ID for reliability.
    The model ID always contains "iPhone" for iPhone devices (e.g. "iPhone14,5").
    """
    name_lower = name.lower()
    if any(kw in name_lower for kw in _IPHONE_KEYWORDS):
        return True
    if model_id and "iphone" in model_id.lower():
        return True
    return False


def is_builtin_camera(name: str, model_id: str = "") -> bool:
    """Return True if *name* looks like a built-in Mac camera.

    Matches all known Apple naming conventions: "FaceTime HD Camera" (Intel),
    "MacBook Air Camera", "MacBook Pro Camera", "iMac Camera", etc. (M-series).
    Excludes iPhone Continuity Cameras and virtual/third-party cameras.
    """
    if is_iphone_camera(name, model_id):
        return False
    name_lower = name.lower()
    if any(kw in name_lower for kw in _VIRTUAL_KEYWORDS):
        return False
    return any(kw in name_lower for kw in _BUILTIN_PATTERNS)


def _enumerate_avfoundation() -> list[tuple[int, str, str, str]]:
    """Enumerate cameras via AVFoundation (same order as OpenCV).

    Returns list of (index, name, unique_id, model_id).
    """
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo)
        result = []
        for i, device in enumerate(devices):
            name = str(device.localizedName())
            unique_id = str(device.uniqueID())
            model_id = str(device.modelID())
            result.append((i, name, unique_id, model_id))
        logger.info("AVFoundation cameras: %s", [(i, n) for i, n, _, _ in result])
        return result
    except Exception as e:
        logger.debug("AVFoundation enumeration failed: %s", e)
        return []


def _enumerate_system_profiler() -> list[tuple[int, str, str, str]]:
    """Fallback: enumerate cameras via system_profiler.

    WARNING: Index order may not match OpenCV's AVFoundation order.
    Returns list of (index, name, unique_id, model_id).
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = json.loads(result.stdout)
        cameras = data.get("SPCameraDataType", [])
        out = []
        for i, cam in enumerate(cameras):
            name = cam.get("_name", f"Camera {i}")
            unique_id = cam.get("spcamera_unique-id", "")
            model_id = cam.get("spcamera_model-id", "")
            out.append((i, name, unique_id, model_id))
        logger.info("system_profiler cameras (fallback): %s", [(i, n) for i, n, _, _ in out])
        return out
    except Exception as e:
        logger.debug("Failed to enumerate cameras via system_profiler: %s", e)
        return []


def _ensure_cache() -> list[tuple[int, str, str, str]]:
    """Populate and return the camera cache."""
    global _camera_cache

    if sys.platform != "darwin":
        _camera_cache = _camera_cache or []
        return _camera_cache

    if _camera_cache is None:
        _camera_cache = _enumerate_avfoundation()
        if not _camera_cache:
            _camera_cache = _enumerate_system_profiler()

    return _camera_cache


def list_camera_names(exclude_iphone: bool = False) -> list[tuple[int, str]]:
    """Return a list of (index, human-readable name) for connected cameras.

    On macOS, queries AVFoundation (preferred) or system_profiler (fallback).
    On other platforms or on error, returns an empty list.

    Results are cached for the lifetime of the process to avoid repeated calls.
    """
    cameras = _ensure_cache()

    if exclude_iphone:
        return [(i, n) for i, n, _, m in cameras if not is_iphone_camera(n, m)]
    return [(i, n) for i, n, _, _ in cameras]


def list_cameras_full() -> list[tuple[int, str, str]]:
    """Return (index, name, unique_id) for all connected cameras.

    This is the extended version of list_camera_names() that includes
    the stable unique_id for cross-session camera matching.
    """
    cameras = _ensure_cache()
    return [(i, n, uid) for i, n, uid, _ in cameras]


def invalidate_cache() -> None:
    """Clear the camera cache so the next call re-queries."""
    global _camera_cache
    _camera_cache = None


def get_camera_name(index: int) -> str:
    """Return the human-readable name for a camera at the given index.

    Returns "Camera N" if the name cannot be determined.
    """
    for i, name, _, _ in _ensure_cache():
        if i == index:
            return name
    return f"Camera {index}"


def get_camera_info(index: int) -> tuple[str, str] | None:
    """Return (name, unique_id) for a camera at the given index, or None."""
    for i, name, uid, _ in _ensure_cache():
        if i == index:
            return (name, uid)
    return None


def find_builtin_camera_index() -> int | None:
    """Find the index of the built-in camera on macOS.

    Matches all known Apple camera names: FaceTime, MacBook Air/Pro Camera,
    iMac Camera, etc. Returns None if no built-in camera is found.
    """
    for index, name, _, model_id in _ensure_cache():
        if is_builtin_camera(name, model_id):
            return index
    return None


def find_first_non_iphone_index() -> int | None:
    """Return the index of the first camera that is not an iPhone.

    Returns None if no non-iPhone camera is found or not on macOS.
    """
    for index, name, _, model_id in _ensure_cache():
        if not is_iphone_camera(name, model_id):
            return index
    return None


def _get_device_max_pixel_area(unique_id: str) -> int | None:
    """Query AVFoundation for a device's max supported resolution (w*h).

    This is a hardware characteristic that uniquely identifies the physical
    camera, regardless of enumeration order.
    """
    try:
        from AVFoundation import AVCaptureDevice
        from CoreMedia import CMVideoFormatDescriptionGetDimensions

        device = AVCaptureDevice.deviceWithUniqueID_(unique_id)
        if device is None:
            return None

        max_area = 0
        for fmt in device.formats():
            dims = CMVideoFormatDescriptionGetDimensions(fmt.formatDescription())
            area = dims.width * dims.height
            if area > max_area:
                max_area = area
        return max_area if max_area > 0 else None
    except Exception as e:
        logger.debug("Failed to query device capabilities: %s", e)
        return None


def _get_opencv_max_pixel_area(index: int) -> int | None:
    """Open an OpenCV camera index and determine its max supported resolution."""
    try:
        import cv2
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            return None
        # Request absurdly high resolution — OpenCV clamps to camera's max
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 9999)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 9999)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return w * h if w > 0 and h > 0 else None
    except Exception as e:
        logger.debug("Failed to probe OpenCV index %d: %s", index, e)
        return None


def find_opencv_index_for_device(unique_id: str) -> int | None:
    """Find the correct OpenCV index for an AVFoundation device by fingerprinting.

    AVFoundation and OpenCV can enumerate cameras in different orders.
    This function matches by comparing each camera's max supported resolution
    (a hardware characteristic) between AVFoundation and OpenCV.

    Returns the verified OpenCV index, or None if no match found.
    """
    target_area = _get_device_max_pixel_area(unique_id)
    if target_area is None:
        logger.warning("Cannot get capabilities for device %s", unique_id)
        return None

    num_cameras = len(_ensure_cache())
    logger.info(
        "Fingerprinting %d OpenCV indices for device %s (target area=%d)",
        num_cameras, unique_id, target_area,
    )

    for i in range(num_cameras):
        opencv_area = _get_opencv_max_pixel_area(i)
        if opencv_area is not None:
            logger.debug("  OpenCV index %d: max pixel area=%d", i, opencv_area)
            if opencv_area == target_area:
                logger.info(
                    "Matched device %s to OpenCV index %d (area=%d)",
                    unique_id, i, target_area,
                )
                return i

    logger.warning("No OpenCV index matched device %s (target area=%d)", unique_id, target_area)
    return None


def resolve_camera_id_to_index(unique_id: str) -> int | None:
    """Find the correct OpenCV index for a camera by its stable unique ID.

    Uses fingerprinting (max resolution comparison) to find the actual
    OpenCV index, since AVFoundation and OpenCV can enumerate in different
    orders. Falls back to AVFoundation index if fingerprinting fails.
    """
    # First verify the device exists in AVFoundation
    avf_index = None
    for index, _, uid, _ in _ensure_cache():
        if uid == unique_id:
            avf_index = index
            break
    if avf_index is None:
        return None  # Device not connected

    # Fingerprint to find the real OpenCV index
    opencv_index = find_opencv_index_for_device(unique_id)
    if opencv_index is not None:
        return opencv_index

    # Fallback: trust AVFoundation index (may be wrong)
    logger.warning(
        "Fingerprinting failed for device %s, falling back to AVFoundation index %d",
        unique_id, avf_index,
    )
    return avf_index


def resolve_camera_name_to_index(name: str) -> int | None:
    """Find the current index of a camera by its human-readable name.

    Tries exact match first, then case-insensitive containment as a
    fallback (Apple sometimes changes suffixes between OS versions).
    Returns None if no camera with that name is currently connected.
    """
    cameras = _ensure_cache()
    for index, cam_name, _, _ in cameras:
        if cam_name == name:
            return index
    name_lower = name.lower()
    for index, cam_name, _, _ in cameras:
        if name_lower in cam_name.lower() or cam_name.lower() in name_lower:
            return index
    return None
