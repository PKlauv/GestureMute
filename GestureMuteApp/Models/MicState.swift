import Foundation

/// Microphone state matching Python's MicState enum.
enum MicState: String, Codable, CaseIterable {
    case LIVE
    case MUTED
    case LOCKED_MUTE

    var displayName: String {
        switch self {
        case .LIVE: "Microphone Live"
        case .MUTED: "Microphone Muted"
        case .LOCKED_MUTE: "Mute Locked"
        }
    }

    var menuBarIcon: String {
        switch self {
        case .LIVE: "mic.fill"
        case .MUTED: "mic.slash"
        case .LOCKED_MUTE: "mic.slash"
        }
    }
}
