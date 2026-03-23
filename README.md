# GestureMute 👋🔇
Real-time hand-gesture microphone control for macOS using computer vision.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-macOS-black.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

---

## ✨ Key Features
- 🖐️ **Palm mute** — Hold an open palm to mute the microphone
- ✊ **Fist keep muted** — Make a fist to keep the mic muted; release to unmute
- 👍 **Thumbs up/down volume** — Adjust microphone input volume with gestures
- ✊✊ **Two-fist pause** — Make two fists to pause gesture detection
- 🔔 **Sound cues** — Audio feedback on mute/unmute actions
- 💊 **Floating overlay** — Always-on-top pill/dot/bar showing mic state
- ⌨️ **Global hotkey** — Ctrl+Shift+G to toggle detection from any app
- ⚡ **Low latency** — Adaptive frame skipping for responsive control

---

## 🧠 How It Works
1. Capture frames from the built-in webcam via OpenCV
2. Run MediaPipe hand/gesture detection on each frame
3. Classify gesture through a state machine with cooldowns and grace periods
4. Trigger mapped action (mute, unmute, volume adjust, pause)
5. Update the floating overlay and optional preview window

The app runs as a system tray application with a two-phase startup for fast UI visibility (~500ms).

---

## 🛠 Tech Stack
- **Language:** Python 3.10+
- **UI Framework:** PyQt6 (system tray, overlay, settings, toast notifications)
- **Computer Vision:** OpenCV + MediaPipe GestureRecognizer
- **Audio Control:** macOS osascript (AppleScript) for mic volume
- **Global Hotkey:** Quartz Event Taps (requires Accessibility permission)
- **Camera Discovery:** `system_profiler SPCameraDataType` for camera identification

---

## 📂 Repository Structure
```text
GestureMute/
├── main.py                    # Entry point
├── requirements.txt
├── gesturemute/
│   ├── main.py                # App startup, AppController, two-phase init
│   ├── config.py              # Config dataclass with JSON persistence
│   ├── camera/
│   │   ├── capture.py         # OpenCV camera + adaptive frame skip
│   │   └── enumerate.py       # macOS camera discovery via system_profiler
│   ├── gesture/
│   │   ├── engine.py          # MediaPipe gesture recognition worker
│   │   ├── gestures.py        # Gesture/MicState enums
│   │   └── state_machine.py   # Gesture state transitions
│   ├── audio/
│   │   ├── macos.py           # macOS mic control via osascript
│   │   └── sounds.py          # WAV sound cue playback
│   ├── events/
│   │   └── bus.py             # Thread-safe pub/sub event bus
│   └── ui/
│       ├── overlay.py         # Floating status indicator (dot/pill/bar)
│       ├── tray.py            # System tray icon and menu
│       ├── settings.py        # Settings panel with camera probe
│       ├── toast.py           # Toast notifications
│       ├── hotkey.py          # Global hotkey (macOS + Windows)
│       ├── preview.py         # Debug preview window
│       ├── onboarding.py      # First-run wizard
│       └── theme.py           # Colors and styling constants
├── README.md
└── LICENSE
```

---

## 🚀 Getting Started

### Prerequisites
- macOS 12+ (Monterey or later)
- Python 3.10+
- A built-in or USB webcam

### 1) Clone the repository
```bash
git clone https://github.com/PKlauv/GestureMute.git
cd GestureMute
```

### 2) Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Run the app
```bash
python main.py
```

### macOS Permissions
On first launch, macOS will prompt for:
- **Camera access** — required for gesture detection
- **Accessibility** — required for the global hotkey (Ctrl+Shift+G). Grant in: System Settings > Privacy & Security > Accessibility

---

## ⚙️ Configuration
Settings are stored at `~/Library/Application Support/GestureMute/config.json` and can be adjusted through the Settings panel (right-click the overlay or tray icon):

- **Camera selection** — auto-detects built-in camera, avoids iPhone Continuity Camera
- **Confidence thresholds** — per-gesture sensitivity tuning
- **Gesture cooldown / activation delay** — timing for state transitions
- **Frame skip** — manual or adaptive mode for CPU usage control
- **Overlay style** — dot, pill, or bar
- **Volume step** — percentage change per thumbs up/down cycle
- **Sound cues** — toggle audio feedback on/off

---

## 🗺 Roadmap: Full macOS Conversion

GestureMute is transitioning from cross-platform to **macOS-native**. Planned work:

| Priority | Item | Status |
|----------|------|--------|
| 🔴 High | Native `.app` bundle via py2app or PyInstaller | Planned |
| 🔴 High | Code-sign and notarize for Gatekeeper | Planned |
| 🟡 Medium | Replace OpenCV camera with AVFoundation (pyobjc) for reliable camera identity | Planned |
| 🟡 Medium | Launch at Login via LaunchAgent or Login Items | Planned |
| 🟡 Medium | DMG installer with drag-to-Applications | Planned |
| 🟢 Low | Replace QSystemTrayIcon with native NSStatusItem | Planned |
| 🟢 Low | Drop Windows audio backends (pycaw/comtypes) | Planned |
| 🟢 Low | Accessibility permission onboarding flow | Planned |

---
<!--
## 📸 Demo
![GestureMute Demo](docs/demo.gif)
-->

## 🤝 Contributing
Contributions, issues, and feature requests are welcome.
If you'd like to improve detection quality, UX, or macOS integration, feel free to open a PR.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## 👤 Author
**Per Kristian Lauvstad**

GitHub: [@PKlauv](https://github.com/PKlauv)