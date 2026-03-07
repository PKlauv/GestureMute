# GestureMute

Hands-free microphone control via webcam gesture recognition.

A desktop system tray app that detects hand gestures through a standard webcam and translates them into mic mute/unmute/volume actions. No hardware buttons needed — just your hand.

**Status:** Phase 2 complete — system tray app with overlay status dot, camera capture, and gesture engine.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Gestures

| Gesture | Action |
|---------|--------|
| Open Palm (hold) | Hold-to-mute (release unmutes) |
| Palm -> Fist | Lock mute ON |
| Fist -> Palm | Lock mute OFF |
| Thumbs Up | Volume +5% (hold for continuous) |
| Thumbs Down | Volume -5% (hold for continuous) |

## Hotkey

**Ctrl+Shift+G** — toggle gesture recognition on/off.

## Tech Stack

- **Python 3.10+** — type hints, dataclasses, match statements
- **MediaPipe** — hand tracking + gesture classification
- **OpenCV** — webcam capture
- **PyQt6** — system tray, overlay, settings UI
- **pycaw** — Windows mic control

## Testing

```bash
pytest
```
