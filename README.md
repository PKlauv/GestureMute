# GestureMute 👋🔇
Real-time hand-gesture based system for controlling mute/unmute actions using computer vision and Python.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Desktop-lightgrey.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

---

## ✨ Key Features
- 🖐️ **Palm mute** Hold an open palm in front of the camera to mute the microphone.
- ✊ **Fist keep muted** Make a fist to keep the microphone muted. Release fist to unmute.
- 👍 **Thumbs up/down volume** Show a thumbs up/down to change the microphone volume.
- ✊✊**Two-fist detection** Make two fists to turn the camera off
- 🕒 **Real-time feedback** Visual indicators in the UI show current gesture state and actions.
- ⚡ **Low latency** Optimized for responsive control with minimal delay.



---

## 🧠 How It Works (High Level)
1. Capture frames from webcam.
2. Run hand/gesture detection on each frame.
3. Classify gesture state.
4. Trigger mapped action (mute/unmute logic).
5. Render preview with detection feedback.

This architecture emphasizes low-latency inference and stable frame handling for responsive UX.

---

## 🛠 Tech Stack
- **Language:** Python (100%)
- **Core concepts:** Computer Vision, Real-Time Processing, Gesture Classification
- **Project structure:** Script entrypoint + package modules + model assets

---

## 📂 Repository Structure
```text
GestureMute/
├── main.py
├── requirements.txt
├── gesturemute/
├── models/
├── README.md
└── LICENSE
```

---

## 🚀 Getting Started

### 1) Clone the repository
```bash
git clone https://github.com/PKlauv/GestureMute.git
cd GestureMute
```

### 2) Create and activate a virtual environment
**macOS/Linux**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Run the app
```bash
python main.py
```

---

## ⚙️ Configuration Notes
Depending on your implementation, you may want to tune:
- Camera index (`0`, `1`, etc.)
- Detection confidence threshold
- Gesture hold duration / debounce logic
- FPS target / frame skipping logic

These parameters are useful when adapting to different hardware and lighting conditions.

---

## 📈 Recent Development Highlights
From recent commits (March 2026):
- Improved **dynamic FPS handling**
- Added **two-fist detection in preview**
- Performed **code cleanup**

These updates focus on better responsiveness and cleaner maintainability.

---
<!--
## 📸 Demo
Add your demo assets here:
- `docs/demo.gif`
- `docs/demo.mp4`
- Screenshots of detection overlays

Example markdown:
```markdown
![GestureMute Demo](docs/demo.gif)
```
-->
---

## 🤝 Contributing
Contributions, issues, and feature requests are welcome.  
If you’d like to improve detection quality, UX feedback overlays, or platform integrations, feel free to open a PR.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## 👤 Author
**Per Kristian Lauvstad**  
GitHub: [@PKlauv](https://github.com/PKlauv)