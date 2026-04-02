"""MediaPipe gesture model download and verification."""

import hashlib
import logging
import socket
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"
)
MODEL_SHA256 = "97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482"

_DOWNLOAD_TIMEOUT_S = 60


def ensure_model(model_path: str) -> None:
    """Download the MediaPipe gesture recognizer model if not present.

    Downloads with a 60s timeout, retries once on failure.

    Args:
        model_path: Path where the model file should exist.

    Raises:
        RuntimeError: If the model cannot be downloaded after 2 attempts.
    """
    path = Path(model_path)
    if path.exists():
        if path.stat().st_size > 0:
            return
        logger.warning("Model file at %s is empty, re-downloading", path)
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            print(f"Downloading gesture model to {path} (attempt {attempt + 1})...")
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(_DOWNLOAD_TIMEOUT_S)
            try:
                urllib.request.urlretrieve(MODEL_URL, path, reporthook=None)
            finally:
                socket.setdefaulttimeout(old_timeout)
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if file_hash != MODEL_SHA256:
                logger.warning(
                    "Model hash mismatch: expected %s, got %s",
                    MODEL_SHA256, file_hash,
                )
                path.unlink()
                raise RuntimeError("Model file hash verification failed")
            print("Download complete (hash verified).")
            return
        except Exception as e:
            logger.warning("Model download attempt %d failed: %s", attempt + 1, e)
            last_error = e
            if path.exists():
                path.unlink()
            if attempt == 0:
                continue

    raise RuntimeError(
        f"Failed to download gesture model after 2 attempts: {last_error}"
    )
