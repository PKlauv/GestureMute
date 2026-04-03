import AppKit
import Foundation
import os
import SwiftUI

/// Central application state. Owns the Python bridge, config, and permissions.
@Observable
final class AppViewModel {
    // State
    var micState: MicState = .LIVE
    var detectionActive = false
    var isEngineReady = false
    var lastGesture: GestureType?
    var lastConfidence: Double = 0
    var cameraName: String?
    var availableCameras: [CameraInfo] = []
    var inputVolume: Int = 100

    // Services
    let bridge = PythonBridge()
    let configManager = ConfigManager()
    let permissions = PermissionsChecker()
    private let hotkey = HotkeyManager()
    private let logger = Logger(subsystem: "com.gesturemute.app", category: "AppViewModel")
    private var configDebounceTask: DispatchWorkItem?
    private var hasBootstrapped = false
    private var onboardingWindow: NSWindow?

    // Gesture hint tracking
    var shownGestureHints: Set<String> {
        get { Set(UserDefaults.standard.stringArray(forKey: "shownGestureHints") ?? []) }
        set { UserDefaults.standard.set(Array(newValue), forKey: "shownGestureHints") }
    }
    var pendingHint: GestureHint?

    /// Computed menu bar icon name based on state.
    var menuBarIconName: String {
        guard detectionActive else { return "mic.fill" }
        return micState.menuBarIcon
    }

    /// Computed menu bar icon opacity (dimmed when paused).
    var menuBarIconOpacity: Double {
        detectionActive ? 1.0 : 0.4
    }

    var config: AppConfig {
        get { configManager.config }
        set {
            configManager.update(newValue)
            // Debounce IPC to Python — sliders fire rapidly during drag
            configDebounceTask?.cancel()
            let task = DispatchWorkItem { [weak self] in
                guard let self else { return }
                self.bridge.send(.updateConfig(self.configManager.config))
            }
            configDebounceTask = task
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3, execute: task)
        }
    }

    init() {
        bridge.onEvent = { [weak self] type, payload in
            self?.handleEvent(type, payload: payload)
        }

        hotkey.onToggle = { [weak self] in
            self?.toggleDetection()
        }
        hotkey.start()

        cameraName = configManager.config.cameraName
    }

    /// One-time app bootstrap — called from menu bar label's .task.
    func bootstrap() {
        guard !hasBootstrapped else { return }
        hasBootstrapped = true

        bridge.launch()

        if configManager.config.onboardingCompleted {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
                self?.startDetection()
            }
        } else {
            showOnboarding()
        }
    }

    /// Show onboarding as a programmatic NSWindow.
    /// This bypasses SwiftUI scene lifecycle entirely — works reliably on first launch.
    func showOnboarding() {
        let onboardingView = OnboardingView()
            .environment(self)
        let controller = NSHostingController(rootView: onboardingView)
        let window = NSWindow(contentViewController: controller)
        window.title = "Welcome to GestureMute"
        window.setContentSize(NSSize(width: 480, height: 560))
        window.styleMask = [.titled, .closable, .fullSizeContentView]
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovableByWindowBackground = true
        window.level = .floating
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        onboardingWindow = window // retain so ARC doesn't close it
    }

    /// Close the onboarding window.
    func dismissOnboarding() {
        onboardingWindow?.close()
        onboardingWindow = nil
    }

    /// Launch the Python engine.
    func launchEngine() {
        bridge.launch()
    }

    func startDetection() {
        bridge.send(.startDetection)
    }

    func stopDetection() {
        bridge.send(.stopDetection)
    }

    func toggleDetection() {
        if detectionActive {
            stopDetection()
        } else {
            startDetection()
        }
    }

    func refreshCameras() {
        bridge.send(.listCameras)
    }

    func quit() {
        bridge.terminate()
        NSApplication.shared.terminate(nil)
    }

    // MARK: - Event Handling

    private func handleEvent(_ type: String, payload: [String: Any]) {
        switch type {
        case "bridge_ready":
            isEngineReady = true
            logger.info("Bridge ready")

        case "engine_ready":
            logger.info("Gesture engine ready")

        case "camera_ready":
            logger.info("Camera ready")

        case "detection_started":
            detectionActive = true

        case "detection_stopped":
            detectionActive = false

        case "mic_action":
            handleMicAction(payload)

        case "gesture_detected":
            if let gestureName = payload["gesture"] as? String,
               let gesture = GestureType(rawValue: gestureName),
               let confidence = payload["confidence"] as? Double {
                lastGesture = gesture
                lastConfidence = confidence
                checkGestureHints(gesture)
            }

        case "state_changed":
            break // State machine transitions logged by Python

        case "camera_list":
            if let data = try? JSONSerialization.data(withJSONObject: payload),
               let list = try? JSONDecoder().decode(CameraListPayload.self, from: data) {
                availableCameras = list.cameras
            }

        case "status":
            if let active = payload["detection_active"] as? Bool {
                detectionActive = active
            }
            if let state = payload["mic_state"] as? String,
               let mic = MicState(rawValue: state) {
                micState = mic
            }
            if let name = payload["camera_name"] as? String {
                cameraName = name
            }

        case "error":
            let source = payload["source"] as? String ?? "unknown"
            let message = payload["message"] as? String ?? "Unknown error"
            logger.error("Engine error [\(source)]: \(message)")

        case "camera_lost":
            logger.warning("Camera lost")

        case "camera_restored":
            logger.info("Camera restored")

        default:
            logger.debug("Unhandled event: \(type)")
        }
    }

    private func handleMicAction(_ payload: [String: Any]) {
        guard let action = payload["action"] as? String else { return }

        if let stateStr = payload["mic_state"] as? String,
           let state = MicState(rawValue: stateStr) {
            micState = state
        }

        if let value = payload["value"] as? Int {
            switch action {
            case "volume_up", "volume_down":
                inputVolume = value
            default:
                break
            }
        }

        switch action {
        case "mute":
            inputVolume = 0
        case "unmute", "unlock_mute":
            inputVolume = 100
        default:
            break
        }

        // Toast notification
        if configManager.config.toastEnabled {
            ToastManager.shared.show(
                action: action,
                micState: micState,
                value: payload["value"] as? Int ?? 0,
                durationMs: configManager.config.toastDurationMs,
                positionX: configManager.config.toastPositionX,
                positionY: configManager.config.toastPositionY
            )
        }

        // Sound cue
        playSoundCue(for: action)
    }

    private func playSoundCue(for action: String) {
        guard configManager.config.soundCuesEnabled else { return }

        let soundName: String
        switch action {
        case "mute": soundName = "Tink"
        case "unmute", "unlock_mute": soundName = "Pop"
        case "lock_mute": soundName = "Purr"
        default: return
        }

        NSSound(named: soundName)?.play()
    }

    // MARK: - Gesture Hints

    private func checkGestureHints(_ gesture: GestureType) {
        guard configManager.config.onboardingCompleted else { return }

        switch gesture {
        case .OPEN_PALM where !shownGestureHints.contains("fist_lock"):
            showHintIfNeeded(.fistLock)
        case .CLOSED_FIST where !shownGestureHints.contains("two_fists"):
            showHintIfNeeded(.twoFists)
        default:
            break
        }
    }

    private func showHintIfNeeded(_ hint: GestureHint) {
        guard !shownGestureHints.contains(hint.id) else { return }
        pendingHint = hint
    }

    func dismissHint(_ hint: GestureHint) {
        shownGestureHints.insert(hint.id)
        if pendingHint?.id == hint.id {
            pendingHint = nil
        }
    }
}

// MARK: - Gesture Hints

struct GestureHint: Identifiable {
    let id: String
    let emoji: String
    let title: String
    let subtitle: String

    static let openPalm = GestureHint(
        id: "open_palm",
        emoji: "✋",
        title: "Raise your open palm",
        subtitle: "Hold it up to mute your microphone"
    )

    static let fistLock = GestureHint(
        id: "fist_lock",
        emoji: "✊",
        title: "Close your fist to lock",
        subtitle: "Keeps mute on even after lowering your hand"
    )

    static let twoFists = GestureHint(
        id: "two_fists",
        emoji: "🤜🤛",
        title: "Two fists to pause",
        subtitle: "Bring both fists together to pause detection"
    )
}
