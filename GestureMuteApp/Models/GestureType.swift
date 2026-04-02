import Foundation

/// Hand gesture types matching Python's Gesture enum.
enum GestureType: String, Codable, CaseIterable {
    case NONE
    case OPEN_PALM
    case CLOSED_FIST
    case THUMB_UP
    case THUMB_DOWN
    case TWO_FISTS_CLOSE

    var emoji: String {
        switch self {
        case .NONE: "—"
        case .OPEN_PALM: "✋"
        case .CLOSED_FIST: "✊"
        case .THUMB_UP: "👍"
        case .THUMB_DOWN: "👎"
        case .TWO_FISTS_CLOSE: "🤜🤛"
        }
    }

    var displayName: String {
        switch self {
        case .NONE: "None"
        case .OPEN_PALM: "Open Palm"
        case .CLOSED_FIST: "Closed Fist"
        case .THUMB_UP: "Thumb Up"
        case .THUMB_DOWN: "Thumb Down"
        case .TWO_FISTS_CLOSE: "Two Fists Close"
        }
    }

    var actionLabel: String {
        switch self {
        case .NONE: ""
        case .OPEN_PALM: "Mute"
        case .CLOSED_FIST: "Lock Mute"
        case .THUMB_UP: "Volume Up"
        case .THUMB_DOWN: "Volume Down"
        case .TWO_FISTS_CLOSE: "Pause"
        }
    }

    /// Key used in Python's confidence_thresholds dict.
    var configKey: String {
        switch self {
        case .OPEN_PALM: "Open_Palm"
        case .CLOSED_FIST: "Closed_Fist"
        case .THUMB_UP: "Thumb_Up"
        case .THUMB_DOWN: "Thumb_Down"
        case .TWO_FISTS_CLOSE: "Two_Fists_Close"
        case .NONE: "None"
        }
    }
}
