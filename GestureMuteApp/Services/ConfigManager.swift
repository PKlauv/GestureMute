import Foundation
import os

/// Reads and writes ~/Library/Application Support/GestureMute/config.json.
@Observable
final class ConfigManager {
    var config: AppConfig

    private let configURL: URL
    private let logger = Logger(subsystem: "com.gesturemute.app", category: "ConfigManager")

    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let appDir = appSupport.appendingPathComponent("GestureMute")
        configURL = appDir.appendingPathComponent("config.json")

        // Load existing config or use defaults
        if let data = try? Data(contentsOf: configURL),
           let loaded = try? JSONDecoder().decode(AppConfig.self, from: data) {
            config = loaded
        } else {
            config = AppConfig()
        }
    }

    /// Save current config to disk.
    func save() {
        do {
            let dir = configURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(config)

            // Atomic write via temp file
            let tempURL = dir.appendingPathComponent(".config_\(UUID().uuidString).tmp")
            try data.write(to: tempURL, options: .atomic)
            _ = try FileManager.default.replaceItemAt(configURL, withItemAt: tempURL)
            logger.info("Config saved")
        } catch {
            logger.error("Failed to save config: \(error)")
        }
    }

    /// Update config and save to disk.
    func update(_ newConfig: AppConfig) {
        config = newConfig
        save()
    }
}
