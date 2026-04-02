# GestureMute — Native SwiftUI UI Redesign

## Context

GestureMute is a macOS menu bar app that uses webcam hand gesture recognition (MediaPipe/OpenCV) to control the system microphone. The current UI is built with Python/PyQt6 — functional but non-native. This redesign replaces all UI with a native SwiftUI shell while keeping the proven Python gesture engine as an embedded subprocess. The goal: a clean, seamless experience that follows Apple's Human Interface Guidelines.

## Architecture

### Two-Process Model

```
┌─────────────────────┐      stdin (JSON)      ┌─────────────────────┐
│   SwiftUI App       │ ──────────────────────→ │   Python Engine     │
│   (native binary)   │ ←────────────────────── │   (subprocess)      │
│                     │      stdout (JSON)      │                     │
│  • MenuBarExtra     │                         │  • CameraWorker     │
│  • Settings Window  │      stderr (logs)      │  • GestureWorker    │
│  • Onboarding       │ ←────────────────────── │  • StateMachine     │
│  • Toast Overlay    │                         │  • AudioController  │
│  • Hotkey Manager   │                         │  • JsonBridge       │
└─────────────────────┘                         └─────────────────────┘
```

- **SwiftUI app** is the main process. It owns the UI, menu bar presence, hotkey, and app lifecycle.
- **Python engine** runs as a child subprocess launched by the Swift app. No UI, no PyQt6. Communicates via newline-delimited JSON over stdin/stdout. Stderr is captured for diagnostics.
- **Shared config**: Both read/write `~/Library/Application Support/GestureMute/config.json`. Swift writes it and sends `update_config` to Python at runtime.
- **Lifecycle**: Python process is bundled inside the `.app` bundle, launched on app start, terminated on quit. Single app bundle — user double-clicks one thing.

## IPC Protocol

All messages are single-line JSON terminated by `\n` (NDJSON). Envelope: `{"type": "<msg_type>", "payload": {...}}`.

### Swift → Python (Commands)

| Type | Payload | Purpose |
|------|---------|---------|
| `start_detection` | — | Start camera + gesture workers |
| `stop_detection` | — | Stop workers, reset state machine |
| `shutdown` | — | Graceful exit |
| `update_config` | Full config object | Apply new settings at runtime |
| `list_cameras` | — | Request available camera list |
| `get_status` | — | Request current engine status |
| `get_config` | — | Request current config |

### Python → Swift (Events)

| Type | Payload | Purpose |
|------|---------|---------|
| `engine_ready` | — | MediaPipe model loaded |
| `camera_ready` | — | Camera producing frames |
| `detection_started` | — | Workers running |
| `detection_stopped` | — | Workers stopped |
| `mic_action` | `{action, value, mic_state}` | Mute/unmute/lock/volume change |
| `gesture_detected` | `{gesture, confidence}` | Real-time gesture info |
| `state_changed` | `{old_state, new_state}` | State machine transition |
| `camera_list` | `{cameras: [{index, name, unique_id, is_builtin}]}` | Response to `list_cameras` |
| `status` | `{detection_active, mic_state, gesture_state, camera_name}` | Response to `get_status` |
| `config` | Full config object | Response to `get_config` |
| `error` | `{source, message}` | Error from any subsystem |
| `camera_lost` | — | Camera disconnected |
| `camera_restored` | — | Camera reconnected |

### Protocol Notes

- Python reads stdin in a dedicated thread, dispatches to engine.
- Python writes stdout protected by `threading.Lock`.
- Stderr is reserved for Python logging (captured by Swift for diagnostics).
- Swift uses `Process` + `Pipe`, reads stdout via `FileHandle.readabilityHandler`.

## SwiftUI App Structure

### Xcode Project Layout

```
GestureMuteApp/
  GestureMuteApp.xcodeproj
  GestureMuteApp/
    GestureMuteApp.swift                -- @main, MenuBarExtra + Settings scene
    
    Models/
      MicState.swift                    -- enum: live, muted, lockedMute
      GestureType.swift                 -- enum: openPalm, closedFist, thumbUp, thumbDown, twoFistsClose
      AppConfig.swift                   -- struct mirroring Python Config dataclass
      IPCMessage.swift                  -- Codable types for all IPC messages
    
    Services/
      PythonBridge.swift                -- Process lifecycle, stdin/stdout JSON IPC
      ConfigManager.swift               -- Read/write config.json, @Observable
      PermissionsChecker.swift          -- Camera (AVCaptureDevice) + Accessibility (AXIsProcessTrusted)
      HotkeyManager.swift              -- Ctrl+Shift+G via CGEvent tap
    
    ViewModels/
      AppViewModel.swift                -- @Observable, central state, owns PythonBridge
      SettingsViewModel.swift           -- @Observable, edit buffer for settings
      OnboardingViewModel.swift         -- @Observable, step tracking + hint state
    
    Views/
      MenuBar/
        MenuBarView.swift               -- Popover content
        StatusHeaderView.swift          -- Mic state icon + label + camera name
      Settings/
        SettingsView.swift              -- NavigationSplitView with sidebar
        GeneralSettingsView.swift       -- Camera, sound cues, toast duration, hotkey display
        GestureSettingsView.swift       -- Per-gesture confidence sliders, volume step
        TimingSettingsView.swift        -- Cooldown, activation, timeout, grace sliders
        AdvancedSettingsView.swift      -- Frame skip, adaptive toggle
      Onboarding/
        OnboardingView.swift            -- Container with step navigation
        PermissionsStepView.swift       -- Camera + Accessibility permission checks
        CameraSelectionStepView.swift   -- Camera picker with radio-style list
      Shared/
        GestureHintView.swift           -- Contextual hint popover (NSPanel)
        ToastView.swift                 -- Lightweight toast notification (NSPanel)
    
    Resources/
      Assets.xcassets                   -- App icon, menu bar template images
      python_engine/                    -- Bundled Python runtime + engine
    
    Info.plist
    GestureMuteApp.entitlements
```

### Entry Point

```swift
@main
struct GestureMuteApp: App {
    @State private var appViewModel = AppViewModel()
    
    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environment(appViewModel)
        } label: {
            Image(systemName: appViewModel.menuBarIconName)
                .renderingMode(.template)
        }
        .menuBarExtraStyle(.window)
        
        Settings {
            SettingsView()
                .environment(appViewModel)
        }
        
        Window("Welcome to GestureMute", id: "onboarding") {
            OnboardingView()
                .environment(appViewModel)
        }
        .windowResizability(.contentSize)
        .defaultSize(width: 480, height: 560)
    }
}
```

On launch, `AppViewModel.init()` checks `configManager.config.onboardingCompleted`. If false, it opens the onboarding window via `OpenWindowAction(id: "onboarding")`.

### State Management

`AppViewModel` is the single source of truth, using Swift 5.9 `@Observable`:

- Owns `PythonBridge` — manages subprocess lifecycle
- Owns `ConfigManager` — reads/writes config.json
- Published properties: `micState`, `detectionActive`, `isEngineReady`, `lastGesture`, `lastConfidence`, `cameraName`, `availableCameras`
- Methods: `startDetection()`, `stopDetection()`, `toggleDetection()`, `updateConfig(_:)`, `refreshCameras()`

`SettingsViewModel` wraps `AppViewModel.config` and propagates changes live via `update_config`. Each control's `onChange` writes immediately — no Save/Cancel buttons, matching macOS System Settings behavior.

## UI Screens

### Menu Bar Icon

Four states, all **monochrome template images** (no color). The system auto-tints for light/dark mode.

| State | SF Symbol | Notes |
|-------|-----------|-------|
| Live | `mic.fill` | Standard mic |
| Muted | `mic.slash` | Mic with strikethrough |
| Locked Mute | `mic.slash` + `lock.fill` badge | Composited overlay |
| Paused | `mic.fill` at 40% opacity | Dimmed |

Implementation: `Image(systemName:).renderingMode(.template)`. Icons are never colored — matches Bluetooth, Wi-Fi, and other system menu bar icons.

### Menu Bar Popover

Compact popover (280pt wide) shown on menu bar icon click. Contains:

1. **Status header** — Rounded icon (mic state) + "Microphone Live/Muted/Locked" + camera name subtitle
2. **Detection toggle** — Standard Toggle switch
3. **Last gesture** — Emoji + gesture name + confidence percentage (or "None")
4. **Input volume** — Current percentage, shows "(muted)" when 0%
5. **Footer** — "Settings..." link (opens Settings window) + "Quit" link

State colors appear only inside the popover (status icon background), not in the menu bar itself.

### Settings Window

Standard macOS Settings window using `NavigationSplitView` with a sidebar. Four sections:

**General:**
- Camera — Picker dropdown with available cameras
- Sound Cues — Toggle
- Toast Duration — Slider (500ms–5000ms) with value label
- Toggle Detection — Read-only keyboard shortcut display (⌃⇧G as key caps)

**Gestures:**
- Per-gesture confidence thresholds — 5 rows, each with emoji + name + action label + slider (30%–95%) + value readout
  - ✋ Open Palm → Mute (default 50%)
  - ✊ Closed Fist → Lock Mute (default 70%)
  - 👍 Thumb Up → Volume Up (default 55%)
  - 👎 Thumb Down → Volume Down (default 70%)
  - 🤜🤛 Two Fists Close → Pause (default 70%)
- Volume Step — Stepper with +/- buttons (1%–20%, default 3%)

**Timing:**
- Gesture Cooldown — Slider (200ms–2000ms, step 50)
- Activation Delay — Slider (100ms–1000ms, step 50)
- No-Hand Timeout — Slider (1000ms–10000ms, step 500)
- Grace Period — Slider (100ms–1000ms, step 50)
- Volume Repeat Rate — Slider (100ms–2000ms, step 50)

**Advanced:**
- Frame Skip — Stepper (1–10)
- Adaptive Frame Skip — Toggle
- Two Fists Max Distance — Slider (0.1–1.0)

All settings grouped in macOS-style rounded rectangles with section headers in small caps. Changes applied on edit (no Save/Cancel buttons — follows macOS Settings convention).

### Onboarding Flow

Two-step window shown on first launch (`onboarding_completed == false`). Centered, 480×560pt.

**Step 1 — Permissions:**
- App icon + "Welcome to GestureMute" title
- "Control your microphone with hand gestures" subtitle
- Camera access row: icon + label + checkmark (green) or "Grant Access" button
- Accessibility row: icon + label + "Open Settings" button (opens System Settings)
- Camera is required (Continue button disabled until granted). Accessibility is optional.
- Step dots (1 of 2)

**Step 2 — Choose Camera:**
- Camera icon + "Select Your Camera" title
- Radio-style list of available cameras (name + type label: Built-in, USB)
- Built-in camera pre-selected
- "Get Started" button → marks `onboarding_completed = true`, closes window, starts detection
- Step dots (2 of 2)

**Contextual Gesture Hints (post-onboarding):**

Small popover cards that appear near the menu bar icon during the first session. Each shown once, tracked in UserDefaults (`shownGestureHints: Set<String>`).

| Trigger | Hint |
|---------|------|
| 30 seconds after first launch | ✋ "Raise your open palm" — Hold it up to mute |
| After first successful mute | ✊ "Close your fist to lock" — Keeps mute on after lowering hand |
| After first successful lock | 🤜🤛 "Two fists to pause" — Bring both fists together to pause detection |

Each hint has a "Got it" button. Implemented as a lightweight NSPanel anchored below the menu bar icon.

### Toast Notifications

Lightweight NSPanel overlays for mute/unmute/volume feedback. Displayed for `toast_duration_ms` (default 1500ms). Shows action icon + label. Positioned near top-right of screen.

## Python Backend Modifications

### New Entry Point: `gesturemute/bridge.py`

Replaces `main.py` for subprocess mode. No PyQt6 imports.

**`JsonBridge` class:**
- `send(msg_type, payload)` — Write JSON line to stdout (thread-safe via `threading.Lock`)
- `register(msg_type, handler)` — Register handler for incoming message type
- `run_stdin_loop()` — Blocking stdin reader (runs in dedicated thread)

**`EngineController` class:**
- Creates `EventBus`, `GestureStateMachine`, workers, audio controller
- Subscribes to EventBus events → translates to JSON stdout messages
- Registers IPC handlers for commands from Swift
- Manages worker start/stop lifecycle

### Refactoring Required

| File | Change |
|------|--------|
| `gesturemute/camera/capture.py` | `CameraWorker`: `QThread` → `threading.Thread`, `pyqtSignal` → callback functions / EventBus |
| `gesturemute/gesture/engine.py` | `GestureWorker`: `QThread` → `threading.Thread`, `pyqtSignal` → callback functions / EventBus |
| `gesturemute/audio/sounds.py` | Replace `QSoundEffect` with `subprocess.Popen(["afplay", path])` or remove (Swift handles sound) |
| `gesturemute/main.py` | Keep as-is for backward compatibility, or update to import from `bridge.py` |

### What Stays Unchanged

- `gesturemute/config.py` — Config dataclass + JSON persistence
- `gesturemute/events/bus.py` — Thread-safe pub/sub event bus
- `gesturemute/gesture/gestures.py` — Gesture/MicState/GestureState enums
- `gesturemute/gesture/state_machine.py` — Gesture → mic_action logic
- `gesturemute/audio/macos.py` — osascript volume control
- `gesturemute/camera/enumerate.py` — AVFoundation camera discovery

### What Moves to Swift

- Hotkey (Ctrl+Shift+G) — `CGEvent` tap in `HotkeyManager.swift`
- System tray / menu bar — `MenuBarExtra` in SwiftUI
- Settings panel — SwiftUI `Settings` scene
- Onboarding wizard — SwiftUI `Window` scene
- Toast notifications — NSPanel managed from Swift
- Sound cue playback — `NSSound` or `AVAudioPlayer` in Swift

### New Dependencies (engine only)

```
mediapipe>=0.10.0
numpy>=1.24.0
opencv-python>=4.8.0
pyobjc-framework-Quartz>=10.0
pyobjc-framework-AVFoundation>=10.0
```

PyQt6 is no longer needed for the engine subprocess.

## Build & Distribution

### Bundling Python Engine

Use **PyInstaller** to create a self-contained directory bundle:

```bash
pyinstaller --noconfirm --onedir --console \
  --name gesturemute_engine \
  --add-data "models/gesture_recognizer.task:models" \
  --hidden-import mediapipe \
  bridge_main.py
```

Output: `dist/gesturemute_engine/` — contains a native executable + all Python dependencies. No separate Python install required.

### App Bundle Structure

```
GestureMute.app/
  Contents/
    MacOS/
      GestureMuteApp                    -- Swift binary (entry point)
    Resources/
      python_engine/
        gesturemute_engine              -- PyInstaller executable
        _internal/                      -- PyInstaller bundled dependencies
        models/
          gesture_recognizer.task
    Info.plist
    GestureMuteApp.entitlements
```

### Info.plist

```xml
<key>LSUIElement</key>
<true/>                              <!-- Menu bar app, no Dock icon -->
<key>NSCameraUsageDescription</key>
<string>GestureMute needs camera access to detect hand gestures for microphone control.</string>
```

### Entitlements

```xml
<key>com.apple.security.device.camera</key>
<true/>
```

### Code Signing

The bundled PyInstaller output (executable + all `.dylib` files) must be signed with the same team identity. Xcode build phase script:

```bash
codesign --force --deep --sign "$CODE_SIGN_IDENTITY" \
  "$BUILT_PRODUCTS_DIR/$CONTENTS_FOLDER_PATH/Resources/python_engine"
```

### Xcode Build Phases

1. Standard Swift compilation
2. **Run Script**: Build Python engine with PyInstaller (or copy pre-built)
3. **Copy Files**: Copy `python_engine/` into `Resources/`
4. **Run Script**: Code sign the Python engine bundle

## Implementation Phases

### Phase 1: Python Backend Refactor
1. Create `gesturemute/bridge.py` with `JsonBridge` + `EngineController`
2. Refactor `CameraWorker` — `QThread` → `threading.Thread`
3. Refactor `GestureWorker` — `QThread` → `threading.Thread`
4. Create `bridge_main.py` entry script
5. **Verify**: `echo '{"type":"list_cameras"}' | python bridge_main.py` outputs JSON camera list

### Phase 2: Xcode Project + Core Services
1. Create Xcode project (macOS App, SwiftUI, deployment target macOS 13.0+)
2. Implement `IPCMessage.swift` — all Codable message types
3. Implement `PythonBridge.swift` — Process + Pipe + async stdout reading
4. Implement `ConfigManager.swift` — read/write config.json
5. Implement `AppViewModel.swift` — central state, owns bridge + config
6. **Verify**: App launches, Python subprocess starts, `engine_ready` message received

### Phase 3: SwiftUI Views
1. Menu bar icon with template images (4 states)
2. `MenuBarView.swift` — popover with status, toggle, gesture info
3. `SettingsView.swift` — NavigationSplitView with all 4 tabs
4. `ToastView.swift` — NSPanel toast notifications
5. **Verify**: Full round-trip — gesture detected in Python → mic_action → UI updates

### Phase 4: Onboarding
1. `PermissionsChecker.swift` — camera + accessibility checks
2. `OnboardingView.swift` — 2-step flow
3. `GestureHintView.swift` — contextual hints with UserDefaults tracking
4. **Verify**: Fresh launch shows onboarding, permissions work, hints appear

### Phase 5: Bundling & Distribution
1. PyInstaller build script for Python engine
2. Xcode build phases to copy + sign engine
3. Info.plist + entitlements finalization
4. **Verify**: Built `.app` runs standalone — double-click, onboarding, detection, settings all work

## Verification Plan

1. **Unit**: Python bridge responds correctly to all IPC message types (test with piped stdin/stdout)
2. **Integration**: Swift app launches Python subprocess, sends `start_detection`, receives `mic_action` events
3. **UI**: Menu bar icon updates on mic state changes, popover shows correct state
4. **Settings**: Changes in Settings window propagate to Python engine via `update_config`
5. **Onboarding**: Fresh config triggers onboarding, permissions are checked, camera is selectable
6. **Hints**: Contextual hints appear at correct triggers, dismiss permanently
7. **Lifecycle**: App quit terminates Python subprocess cleanly, no orphan processes
8. **Distribution**: Built `.app` bundle runs on a clean Mac (no Python installed)

## Critical Files

| File | Role |
|------|------|
| `gesturemute/config.py` | Config dataclass — contract between Swift `AppConfig` and Python |
| `gesturemute/camera/capture.py` | `CameraWorker` — needs QThread→Thread refactor |
| `gesturemute/gesture/engine.py` | `GestureWorker` — needs QThread→Thread refactor |
| `gesturemute/events/bus.py` | EventBus — stays as-is, bridge subscribes to it |
| `gesturemute/gesture/state_machine.py` | State machine — stays as-is |
| `gesturemute/audio/macos.py` | Audio controller — stays as-is |
| `gesturemute/camera/enumerate.py` | Camera discovery — stays as-is, called by bridge |
| `gesturemute/main.py` | Current entry point — reference for wiring in bridge.py |
