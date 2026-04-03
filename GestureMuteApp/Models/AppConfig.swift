import Foundation

/// Application configuration, mirrors Python Config dataclass.
/// Shared via ~/Library/Application Support/GestureMute/config.json.
struct AppConfig: Codable, Equatable {
    var configVersion: Int = 2
    var cameraIndex: Int = 0
    var confidenceThreshold: Double = 0.7
    var confidenceThresholds: [String: Double] = [
        "Open_Palm": 0.5,
        "Closed_Fist": 0.7,
        "Thumb_Up": 0.55,
        "Thumb_Down": 0.7,
        "Two_Fists_Close": 0.7,
    ]
    var gestureCooldownMs: Int = 500
    var activationDelayMs: Int = 300
    var noHandTimeoutMs: Int = 3000
    var transitionGraceMs: Int = 400
    var volumeStep: Int = 3
    var volumeRepeatMs: Int = 400
    var frameSkip: Int = 1
    var adaptiveFrameSkip: Bool = true
    var modelPath: String = "models/gesture_recognizer.task"
    var toastDurationMs: Int = 1500
    var cameraBackend: String = "auto"
    var overlayStyle: String = "pill"
    var overlayX: Int?
    var overlayY: Int?
    var twoFistsMaxDistance: Double = 0.6
    var onboardingCompleted: Bool = false
    var soundCuesEnabled: Bool = true
    var toastEnabled: Bool = true
    var toastPositionX: Double?
    var toastPositionY: Double?
    var cameraUserOverride: Bool = false
    var cameraName: String?
    var cameraUniqueId: String?

    enum CodingKeys: String, CodingKey {
        case configVersion = "config_version"
        case cameraIndex = "camera_index"
        case confidenceThreshold = "confidence_threshold"
        case confidenceThresholds = "confidence_thresholds"
        case gestureCooldownMs = "gesture_cooldown_ms"
        case activationDelayMs = "activation_delay_ms"
        case noHandTimeoutMs = "no_hand_timeout_ms"
        case transitionGraceMs = "transition_grace_ms"
        case volumeStep = "volume_step"
        case volumeRepeatMs = "volume_repeat_ms"
        case frameSkip = "frame_skip"
        case adaptiveFrameSkip = "adaptive_frame_skip"
        case modelPath = "model_path"
        case toastDurationMs = "toast_duration_ms"
        case cameraBackend = "camera_backend"
        case overlayStyle = "overlay_style"
        case overlayX = "overlay_x"
        case overlayY = "overlay_y"
        case twoFistsMaxDistance = "two_fists_max_distance"
        case onboardingCompleted = "onboarding_completed"
        case soundCuesEnabled = "sound_cues_enabled"
        case toastEnabled = "toast_enabled"
        case toastPositionX = "toast_position_x"
        case toastPositionY = "toast_position_y"
        case cameraUserOverride = "camera_user_override"
        case cameraName = "camera_name"
        case cameraUniqueId = "camera_unique_id"
    }
}
