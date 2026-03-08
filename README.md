# GestureMute

Control your mic with your hand. No buttons, no hotkeys, no fumbling.

<!-- TODO: demo GIF -->
<!-- ![GestureMute Demo](assets/demo.gif) -->

## About

GestureMute watches your webcam for hand gestures and translates them into microphone actions in real time. Hold up your palm to mute. Make a fist to lock it. Thumbs up/down for volume. It runs quietly in your system tray and stays out of the way until you need it.

**Key features:**

- Hold-to-mute with palm detection (release to unmute)
- Lock/unlock mute with palm-to-fist transitions
- Volume control via thumbs up/down gestures
- Floating status overlay (dot or pill style)
- Dark-themed toast notifications on every action
- Per-gesture confidence thresholds for reliable detection
- 400ms grace period for natural gesture transitions
- Settings panel with runtime config (no restart needed)
- First-launch onboarding wizard
- Preview mode for live gesture debugging

### Built With

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Hand Tracking | Google MediaPipe (GestureRecognizer task API) |
| Camera | OpenCV |
| UI | PyQt6 (system tray, overlays, settings, threading) |
| Audio (Windows) | pycaw + comtypes |
| Audio (macOS) | osascript |

## Getting Started

**Requirements:** Python 3.10+, a webcam, Windows or macOS.

```bash
git clone https://github.com/anthropics/gesturemute.git
cd gesturemute
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

First launch opens an onboarding wizard that walks you through gestures, camera access, and overlay setup.After that, GestureMute drops into your system tray.

A floating status dot shows your mic state at a glance: green (live), red (muted), amber (locked mute). Right-click the tray icon for settings, preview mode, or quit.

### Testing

```bash
pytest
```

40 tests covering the state machine, config persistence, and toast manager.

## Gestures

| Gesture | Action |
|---------|--------|
| Open Palm (hold) | Mute while held. Release to unmute. |
| Palm then Fist | Lock mute on |
| Fist then Palm | Unlock mute |
| Thumbs Up | Volume +3% (hold for continuous) |
| Thumbs Down | Volume -3% (hold for continuous) |

Transitions are forgiving. A 400ms grace period lets you move between gestures naturally without false triggers. Each gesture has its own confidence threshold, tuned independently for reliability across different lighting conditions.

## Configuration

### Settings Panel

Open from the system tray menu. Three tabs:

- **General** -- camera index, frame skip, overlay style, toast duration, hotkey display
- **Gestures** -- per-gesture confidence thresholds, cooldown, activation delay, grace period, volume step
- **About** -- version, privacy info, links

Timing and threshold changes apply at runtime. No restart needed.

### Overlay Styles

Two options, switchable in Settings:

- **Dot** -- minimal colored circle, always on top
- **Pill** -- larger indicator with icon and status label

### Hotkey

**Ctrl+Shift+G** toggles gesture recognition on/off. Useful when you need the camera but don't want gestures firing.

### Preview Mode

```bash
python main.py --preview
```

Live debug overlay showing detected gestures, confidence scores, and hand landmarks drawn over the camera feed. Great for calibrating your setup or troubleshooting recognition issues.

## Privacy

No frames are stored or transmitted. Every frame is processed in memory and discarded immediately. Zero data leaves your machine.

## License

[MIT](LICENSE)
