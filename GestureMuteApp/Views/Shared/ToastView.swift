import AppKit
import SwiftUI

/// NSView subclass that makes its parent window draggable via mouse events,
/// clamped to the screen's visible frame.
private final class DraggableHostingView<Content: View>: NSHostingView<Content> {
    private var initialMouseLocation: NSPoint = .zero
    private var initialWindowOrigin: NSPoint = .zero

    override func mouseDown(with event: NSEvent) {
        initialMouseLocation = NSEvent.mouseLocation
        initialWindowOrigin = window?.frame.origin ?? .zero
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window else { return }
        guard let screen = NSScreen.main else { return }

        let currentMouse = NSEvent.mouseLocation
        let dx = currentMouse.x - initialMouseLocation.x
        let dy = currentMouse.y - initialMouseLocation.y

        var newOrigin = NSPoint(
            x: initialWindowOrigin.x + dx,
            y: initialWindowOrigin.y + dy
        )

        // Clamp to visible frame
        let visible = screen.visibleFrame
        newOrigin.x = max(visible.minX, min(newOrigin.x, visible.maxX - window.frame.width))
        newOrigin.y = max(visible.minY, min(newOrigin.y, visible.maxY - window.frame.height))

        window.setFrameOrigin(newOrigin)
    }
}

/// Manages lightweight toast notification overlays.
final class ToastManager {
    static let shared = ToastManager()

    private var panel: NSPanel?
    private var previewPanel: NSPanel?
    private var dismissTimer: Timer?

    /// Whether the preview toast is currently showing (suppresses real toasts).
    var isShowingPreview: Bool { previewPanel != nil }

    /// Show a toast notification at the configured position.
    func show(
        action: String,
        micState: MicState,
        value: Int = 0,
        durationMs: Int = 1500,
        positionX: Double? = nil,
        positionY: Double? = nil
    ) {
        // Suppress real toasts while the preview is visible
        if isShowingPreview { return }

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
            self?.showPanel(
                icon: content.icon,
                label: content.label,
                color: content.color,
                durationMs: durationMs,
                positionX: positionX,
                positionY: positionY
            )
        }
    }

    /// Show a draggable preview toast at the given position (or default top-right).
    func showPreview(positionX: Double?, positionY: Double?) {
        DispatchQueue.main.async { [weak self] in
            self?.showPreviewPanel(positionX: positionX, positionY: positionY)
        }
    }

    /// Dismiss the preview toast.
    func dismissPreview() {
        DispatchQueue.main.async { [weak self] in
            self?.previewPanel?.orderOut(nil)
            self?.previewPanel = nil
        }
    }

    /// Returns the current preview position as screen percentages (0.0–1.0), or nil if not showing.
    func currentPreviewPosition() -> (x: Double, y: Double)? {
        guard let panel = previewPanel, let screen = NSScreen.main else { return nil }
        let visible = screen.visibleFrame

        let availableWidth = visible.width - panel.frame.width
        let availableHeight = visible.height - panel.frame.height
        guard availableWidth > 0, availableHeight > 0 else { return nil }

        let x = (panel.frame.origin.x - visible.origin.x) / availableWidth
        let y = (panel.frame.origin.y - visible.origin.y) / availableHeight

        return (
            x: min(1, max(0, x)),
            y: min(1, max(0, y))
        )
    }

    /// Move the preview toast to a specific position (used by Reset to Default).
    func movePreview(positionX: Double?, positionY: Double?) {
        guard let panel = previewPanel, let screen = NSScreen.main else { return }
        let origin = Self.calculateOrigin(
            positionX: positionX,
            positionY: positionY,
            panelWidth: panel.frame.width,
            panelHeight: panel.frame.height,
            visibleFrame: screen.visibleFrame
        )
        panel.setFrameOrigin(origin)
    }

    // MARK: - Private

    private static func calculateOrigin(
        positionX: Double?,
        positionY: Double?,
        panelWidth: CGFloat,
        panelHeight: CGFloat,
        visibleFrame: NSRect
    ) -> NSPoint {
        if let px = positionX, let py = positionY {
            let x = visibleFrame.origin.x + CGFloat(px) * (visibleFrame.width - panelWidth)
            let y = visibleFrame.origin.y + CGFloat(py) * (visibleFrame.height - panelHeight)
            return NSPoint(x: x, y: y)
        }
        // Default: top-right
        return NSPoint(
            x: visibleFrame.maxX - panelWidth - 20,
            y: visibleFrame.maxY - panelHeight - 10
        )
    }

    private func showPanel(
        icon: String,
        label: String,
        color: NSColor,
        durationMs: Int,
        positionX: Double?,
        positionY: Double?
    ) {
        dismissTimer?.invalidate()
        panel?.orderOut(nil)

        guard let screen = NSScreen.main else { return }
        let panelWidth: CGFloat = 180
        let panelHeight: CGFloat = 44

        let origin = Self.calculateOrigin(
            positionX: positionX,
            positionY: positionY,
            panelWidth: panelWidth,
            panelHeight: panelHeight,
            visibleFrame: screen.visibleFrame
        )

        let panel = NSPanel(
            contentRect: NSRect(x: origin.x, y: origin.y, width: panelWidth, height: panelHeight),
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

    private func showPreviewPanel(positionX: Double?, positionY: Double?) {
        previewPanel?.orderOut(nil)

        guard let screen = NSScreen.main else { return }
        let panelWidth: CGFloat = 180
        let panelHeight: CGFloat = 44

        let origin = Self.calculateOrigin(
            positionX: positionX,
            positionY: positionY,
            panelWidth: panelWidth,
            panelHeight: panelHeight,
            visibleFrame: screen.visibleFrame
        )

        let panel = NSPanel(
            contentRect: NSRect(x: origin.x, y: origin.y, width: panelWidth, height: panelHeight),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary]

        let previewContent = HStack(spacing: 8) {
            Image(systemName: "bell.fill")
                .foregroundStyle(.white.opacity(0.8))
                .font(.system(size: 16))
            Text("Toast Preview")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial, in: Capsule())
        .overlay(
            Capsule()
                .strokeBorder(.white.opacity(0.3), style: StrokeStyle(lineWidth: 1.5, dash: [6, 4]))
        )

        let hostingView = DraggableHostingView(rootView: previewContent)
        panel.contentView = hostingView
        panel.orderFront(nil)
        self.previewPanel = panel
    }
}
