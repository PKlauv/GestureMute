# GestureMute

**Hands-free microphone control for macOS, powered by computer vision.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS-black.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

<!-- Add a hero GIF or screenshot here showing GestureMute in action -->
<!-- ![GestureMute Demo](docs/demo.gif) -->

---

## Why GestureMute?

Ever been filming a presentation, stepped away from your laptop, and needed to mute your mic? GestureMute lets you control your microphone with hand gestures — no keyboard, no mouse, no interruptions. Just raise your palm.

It's useful for anyone who needs hands-free mic control: remote presentations, podcast recording, live streaming, video calls, or any situation where you're not sitting right in front of your machine.

---

## Key Features

- **Palm mute** — Hold an open palm to mute the microphone
- **Fist lock** — Make a fist to keep the mic muted; release to unmute
- **Thumbs up/down** — Adjust microphone input volume with gestures
- **Two-fist pause** — Make two fists to pause gesture detection entirely
- **Sound cues** — Audio feedback so you know when you've muted/unmuted
- **Global hotkey** — `Ctrl+Shift+G` to toggle detection from any app
- **Low latency** — Adaptive frame skipping keeps things responsive

---

## How It Works

1. Your webcam captures video frames in real time
2. MediaPipe detects your hand gestures with confidence scoring
3. A state machine translates gestures into microphone actions (mute, unmute, volume adjust)
4. The menu bar icon updates and you get visual + audio feedback

<!-- 📊 Add a diagram or GIF here showing the gesture detection flow -->

---

## Gestures

| Gesture | Action | Description |
|---------|--------|-------------|
| ✋ Open Palm | Mute | Hold palm facing camera to mute |
| ✊ Closed Fist | Lock Mute | Keeps mic muted until you release |
| 👍 Thumbs Up | Volume Up | Increases mic input volume |
| 👎 Thumbs Down | Volume Down | Decreases mic input volume |
| ✊✊ Two Fists | Pause | Pauses all gesture detection |

<!-- 🖼️ Add GIFs or images demonstrating each gesture here -->

---

## Getting Started

### Prerequisites

- macOS 12+ (Monterey or later)
- Python 3.10+
- A built-in or USB webcam

### Installation

```bash
git clone https://github.com/PKLauv/GestureMute.git
cd GestureMute
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### macOS Permissions

On first launch, macOS will prompt for:

- **Camera access** — required for gesture detection
- **Accessibility** — required for the global hotkey. Grant in: *System Settings > Privacy & Security > Accessibility*

> **Tip:** If you have an iPhone nearby, disable Continuity Camera to prevent it from interfering with camera detection. On your iPhone: *Settings > General > AirPlay & Handoff > Continuity Camera* (toggle off).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Menu bar UI | Swift + SwiftUI (native macOS) |
| Gesture engine | Python 3.10+ (subprocess) |
| Computer vision | OpenCV + MediaPipe |
| Mic control | AppleScript via `osascript` |
| Global hotkey | Quartz Event Taps |
| IPC | JSON-line protocol (stdin/stdout) |

### Project Structure

```
GestureMute/
├── GestureMuteApp/       # Swift/SwiftUI native menu bar app
├── gesturemute/           # Python gesture engine
│   ├── camera/            # Webcam capture & enumeration
│   ├── gesture/           # MediaPipe detection & state machine
│   ├── audio/             # macOS mic control & sound cues
│   ├── events/            # Thread-safe event bus
│   └── ui/                # Legacy PyQt6 UI components
├── main.py                # Entry point
├── bridge_main.py         # IPC bridge entry point
└── requirements.txt
```

---

## Roadmap

GestureMute is heading toward becoming a fully packaged macOS app. Here's what's planned:

- **Native `.app` bundle** — Distributable via GitHub Releases as a downloadable app
- **Code signing & notarization** — So macOS Gatekeeper doesn't block it
- **DMG installer** — Drag-to-Applications installation
- **Launch at Login** — Start automatically via LaunchAgent or Login Items
- **AVFoundation camera** — Replace OpenCV camera layer with native macOS APIs

The long-term goal is a one-click install: download from Releases, drag to Applications, and you're good to go.

---

## Contributing

Contributions, issues, and feature requests are welcome! Whether it's improving gesture detection accuracy, UX polish, or macOS integration — feel free to open an issue or submit a PR, it is greatly appreciated! 

---

## License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.

---

**Built by [PKLauv](https://github.com/PKLauv)**
