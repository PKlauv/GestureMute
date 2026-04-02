import AppKit
import AVFoundation
import Foundation
import os

/// Checks camera and accessibility permissions.
@Observable
final class PermissionsChecker {
    var cameraAuthorized = false
    var accessibilityEnabled = false

    private let logger = Logger(subsystem: "com.gesturemute.app", category: "Permissions")

    init() {
        checkAll()
    }

    /// Re-check all permission states.
    func checkAll() {
        checkCamera()
        checkAccessibility()
    }

    func checkCamera() {
        let status = AVCaptureDevice.authorizationStatus(for: .video)
        cameraAuthorized = (status == .authorized)
    }

    func checkAccessibility() {
        accessibilityEnabled = AXIsProcessTrusted()
    }

    /// Request camera permission. Calls completion on main thread.
    func requestCameraAccess(completion: @escaping (Bool) -> Void) {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                self?.cameraAuthorized = granted
                completion(granted)
            }
        }
    }

    /// Open System Settings > Accessibility for the user to grant access.
    func openAccessibilitySettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }
}
