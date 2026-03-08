# GestureMute

Mute your mic with your hand. No buttons, no hotkeys, no fumbling.

GestureMute watches your webcam for hand gestures and translates them into microphone actions in real time. Hold up your palm to mute. Make a fist to lock it. Thumbs up/down for volume. That's it.

**Status:** Fully functional. Core pipeline, UI, settings, toast notifications, and onboarding are all implemented and tested.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

First launch walks you through a quick onboarding wizard: gesture tutorial, camera access, and overlay preferences.

## Gestures

| Gesture | Action |
|---------|--------|
| Open Palm (hold) | Hold-to-mute. Release to unmute. |
| Palm then Fist | Lock mute ON |
| Fist then Palm | Lock mute OFF |
| Thumbs Up | Volume +5% (hold for continuous) |
| Thumbs Down | Volume -5% (hold for continuous) |

Transitions are forgiving. A 400ms grace period lets you move between gestures naturally without triggering the wrong state. Per-gesture confidence thresholds mean each gesture is tuned independently, so Open Palm and Thumbs Up work reliably even in tricky lighting.

Gesture feedback appears as dark-themed toast popups so you always know what was recognized.

## Overlay

A floating indicator shows your current mic state at a glance. Two styles available:

- **Dot** - minimal colored circle
- **Pill** - larger indicator with icon and label

Switch between them in Settings.

## Settings

Open from the system tray menu. Three tabs:

- **General** - overlay style (dot/pill), overlay position, startup behavior
- **Gestures** - confidence thresholds, cooldown timing, activation delay
- **About** - version info and links

## Hotkey

**Ctrl+Shift+G** toggles gesture recognition on/off. Useful when you need the camera but don't want gestures firing.

## Preview Mode

```bash
python main.py --preview
```

Shows a live debug overlay with detected gestures, confidence scores, and hand landmarks. Great for calibrating your setup or just seeing what the engine sees.

## Tech Stack

- **Python 3.10+** with type hints and dataclasses throughout
- **MediaPipe** for hand tracking and gesture classification
- **OpenCV** for webcam capture
- **PyQt6** for the system tray, overlay, and threading
- **pycaw** for Windows mic control

## Testing

```bash
pytest
```

## Privacy

No frames are stored or transmitted. Everything is processed in memory and discarded immediately.
