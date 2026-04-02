import AppKit
import SwiftUI

/// Manages lightweight toast notification overlays.
final class ToastManager {
    static let shared = ToastManager()

    private var panel: NSPanel?
    private var dismissTimer: Timer?

    /// Show a toast notification near the top-right of the screen.
    func show(action: String, micState: MicState, value: Int = 0, durationMs: Int = 1500) {
        let content: (icon: String, label: String, color: NSColor)

        switch action {
        case "mute":
            content = ("mic.slash.fill", "Muted", .systemRed)
        case "unmute":
            content = ("mic.fill", "Live", .systemGreen)
        case "lock_mute":
            content = ("lock.fill", "Mute Locked", .systemOrange)
        case "unlock_mute":
            content = ("lock.open.fill", "Unlocked", .systemGreen)
        case "volume_up":
            content = ("speaker.wave.2.fill", "Volume: \(value)%", .white)
        case "volume_down":
            content = ("speaker.wave.1.fill", "Volume: \(value)%", .white)
        case "pause_detection":
            content = ("pause.fill", "Detection Paused", .systemGray)
        default:
            return
        }

        DispatchQueue.main.async { [weak self] in
            self?.showPanel(icon: content.icon, label: content.label, color: content.color, durationMs: durationMs)
        }
    }

    private func showPanel(icon: String, label: String, color: NSColor, durationMs: Int) {
        dismissTimer?.invalidate()

        // Remove existing panel
        panel?.orderOut(nil)

        guard let screen = NSScreen.main else { return }
        let panelWidth: CGFloat = 180
        let panelHeight: CGFloat = 44
        let x = screen.visibleFrame.maxX - panelWidth - 20
        let y = screen.visibleFrame.maxY - panelHeight - 10

        let panel = NSPanel(
            contentRect: NSRect(x: x, y: y, width: panelWidth, height: panelHeight),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary]

        let hostingView = NSHostingView(rootView:
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundStyle(Color(nsColor: color))
                    .font(.system(size: 16))
                Text(label)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(.white)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(.ultraThinMaterial, in: Capsule())
        )
        panel.contentView = hostingView
        panel.orderFront(nil)
        self.panel = panel

        dismissTimer = Timer.scheduledTimer(withTimeInterval: Double(durationMs) / 1000, repeats: false) { [weak self] _ in
            self?.panel?.orderOut(nil)
            self?.panel = nil
        }
    }
}
