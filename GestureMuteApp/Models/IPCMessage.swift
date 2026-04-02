import Foundation

// MARK: - Envelope

/// Generic IPC message envelope for JSON-line protocol.
struct IPCMessage: Codable {
    let type: String
    let payload: AnyCodable?

    init(type: String, payload: AnyCodable? = nil) {
        self.type = type
        self.payload = payload
    }
}

// MARK: - Swift → Python Commands

enum IPCCommand {
    case startDetection
    case stopDetection
    case shutdown
    case updateConfig(AppConfig)
    case listCameras
    case getStatus
    case getConfig

    func encode() -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase

        let message: IPCMessage
        switch self {
        case .startDetection:
            message = IPCMessage(type: "start_detection")
        case .stopDetection:
            message = IPCMessage(type: "stop_detection")
        case .shutdown:
            message = IPCMessage(type: "shutdown")
        case .updateConfig(let config):
            let configData = try! encoder.encode(config)
            let configDict = try! JSONSerialization.jsonObject(with: configData) as! [String: Any]
            message = IPCMessage(type: "update_config", payload: AnyCodable(configDict))
        case .listCameras:
            message = IPCMessage(type: "list_cameras")
        case .getStatus:
            message = IPCMessage(type: "get_status")
        case .getConfig:
            message = IPCMessage(type: "get_config")
        }

        var data = try! encoder.encode(message)
        data.append(0x0A) // newline
        return data
    }
}

// MARK: - Python → Swift Events

struct MicActionPayload: Codable {
    let action: String
    let value: Int
    let micState: String

    enum CodingKeys: String, CodingKey {
        case action, value
        case micState = "mic_state"
    }
}

struct GestureDetectedPayload: Codable {
    let gesture: String
    let confidence: Double
}

struct StateChangedPayload: Codable {
    let oldState: String
    let newState: String

    enum CodingKeys: String, CodingKey {
        case oldState = "old_state"
        case newState = "new_state"
    }
}

struct CameraInfo: Codable, Identifiable {
    let index: Int
    let name: String
    let uniqueId: String
    let isBuiltin: Bool

    var id: String { uniqueId }

    enum CodingKeys: String, CodingKey {
        case index, name
        case uniqueId = "unique_id"
        case isBuiltin = "is_builtin"
    }
}

struct CameraListPayload: Codable {
    let cameras: [CameraInfo]
}

struct StatusPayload: Codable {
    let detectionActive: Bool
    let micState: String
    let gestureState: String
    let cameraName: String?

    enum CodingKeys: String, CodingKey {
        case detectionActive = "detection_active"
        case micState = "mic_state"
        case gestureState = "gesture_state"
        case cameraName = "camera_name"
    }
}

struct ErrorPayload: Codable {
    let source: String
    let message: String
}

// MARK: - AnyCodable helper

/// Type-erased Codable wrapper for dynamic JSON payloads.
struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues(\.value)
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map(\.value)
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if container.decodeNil() {
            value = NSNull()
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported type")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let string as String:
            try container.encode(string)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let bool as Bool:
            try container.encode(bool)
        case is NSNull:
            try container.encodeNil()
        default:
            try container.encodeNil()
        }
    }
}
