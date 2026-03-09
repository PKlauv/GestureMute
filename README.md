# GestureMute

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)

Control your mic with your hand. No buttons, no hotkeys, no fumbling.

<!-- TODO: demo GIF -->
<!-- ![GestureMute Demo](assets/demo.gif) -->

<details>
<summary><strong>Table of Contents</strong></summary>

- [About](#about)
- [Getting Started](#getting-started)
- [Gestures](#gestures)
- [How It Works](#how-it-works)
- [Performance](#performance)
- [Configuration](#configuration)
- [Privacy](#privacy)
- [License](#license)

</details>

## About

GestureMute watches your webcam for hand gestures and translates them into microphone actions in real time. Hold up your palm to mute. Make a fist to lock it. Thumbs up/down for volume. It runs quietly in your system tray and stays out of the way until you need it.

**Key features:**

- **Palm mute** -- hold to mute, release to unmute. Fist locks it on.
- **Volume gestures** -- thumbs up/down, hold for continuous adjustment
- **Status overlay** -- floating dot, pill, or bar. Always-on-top, DPI-aware.
- **Smart detection** -- per-gesture confidence thresholds, 400ms grace period, auto camera reconnect
- **Settings panel** -- tune everything at runtime. No restart needed.
- **Onboarding + preview** -- first-launch wizard walks you through setup. Preview mode shows live gesture debug.

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
git clone https://github.com/PKlauv/GestureMute.git
cd gesturemute
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

First launch opens an onboarding wizard that walks you through gestures, camera access, and overlay setup. After that, GestureMute drops into your system tray.

A floating status dot shows your mic state at a glance: green (live), red (muted), amber (locked mute), grey (paused). Hover the tray icon to see current mic state. Right-click it for settings, preview mode, or quit.

### Testing

```bash
pytest
```

45 tests covering the state machine, config persistence, and toast manager.

## Gestures

| Gesture | Action |
|---------|--------|
| Open Palm (hold) | Mute while held. Release to unmute. |
| Palm then Fist | Lock mute on |
| Fist then Palm | Unlock mute |
| Thumbs Up | Volume +3% (hold for continuous) |
| Thumbs Down | Volume -3% (hold for continuous) |

Transitions are forgiving. A 400ms grace period lets you move between gestures naturally without false triggers. Each gesture has its own confidence threshold, tuned independently for reliability across different lighting conditions.

## How It Works

```
[Webcam] -> [Camera Thread] -> [Gesture Engine] -> [Event Bus] -> [Audio Controller]
                                                        |
                                                   [UI Layer]
```

The camera thread captures frames on a dedicated `QThread` and feeds them into the gesture engine, which runs MediaPipe inference on every 2nd-3rd frame to keep CPU usage low. A state machine with cooldowns and grace periods filters raw detections into clean gesture events.

Those events flow through a thread-safe event bus (observer pattern) to the audio controller and UI layer. Modules never call each other directly. The audio controller toggles the system mic via platform APIs (pycaw on Windows, osascript on macOS). The UI layer updates the overlay, toasts, and tray icon.

Everything runs off the main Qt event loop except camera capture and gesture inference, which get their own threads. The result: gesture-to-action in under 300ms with no UI jank.

## Performance

| Metric | Target |
|--------|--------|
| Gesture-to-action latency | < 300ms |
| CPU usage (active) | < 8% |
| Memory | < 150 MB |
| Gesture accuracy | > 92% |
| False positive rate | < 2% |
| Startup time | < 3s |
| Frame processing | >= 15 FPS |

## Configuration

### Settings Panel

Open from the system tray menu. Three tabs:

- **General** -- camera index, frame skip, overlay style, toast duration, hotkey display
- **Gestures** -- per-gesture confidence thresholds, cooldown, activation delay, grace period, volume step
- **About** -- version, privacy info, links, re-run setup wizard

Timing and threshold changes apply at runtime. No restart needed.

### Overlay Styles

Three options, switchable in Settings:

- **Dot** -- minimal colored circle, always on top
- **Pill** -- larger indicator with icon and status label
- **Bar** -- wide status bar across the top of the screen

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
