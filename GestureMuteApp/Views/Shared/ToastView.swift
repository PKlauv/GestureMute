import AppKit
import SwiftUI

/// NSView subclass that makes its parent window draggable via mouse events,
/// clamped to the screen's visible frame.
private final class DraggableView: NSView {
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

        let visible = screen.visibleFrame
        newOrigin.x = max(visible.minX, min(newOrigin.x, visible.maxX - window.frame.width))
        newOrigin.y = max(visible.minY, min(newOrigin.y, visible.maxY - window.frame.height))

        window.setFrameOrigin(newOrigin)
    }
}

// MARK: - Toast capsule (pure AppKit)

/// Builds a capsule-shaped toast view using NSVisualEffectView + NSImageView + NSTextField.
private func makeToastCapsule(
    icon: String,
    label: String,
    iconColor: NSColor,
    width: CGFloat,
    height: CGFloat,
    dashed: Bool = false,
    draggable: Bool = false
) -> NSView {
    let container: NSView = draggable ? DraggableView(frame: NSRect(x: 0, y: 0, width: width, height: height))
                                      : NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
    container.wantsLayer = true

    // Capsule mask
    let maskLayer = CAShapeLayer()
    maskLayer.path = NSBezierPath(roundedRect: container.bounds, xRadius: height / 2, yRadius: height / 2).cgPath
    container.layer?.mask = maskLayer

    // Vibrancy background
    let effectView = NSVisualEffectView(frame: container.bounds)
    effectView.material = .hudWindow
    effectView.state = .active
    effectView.blendingMode = .behindWindow
    effectView.autoresizingMask = [.width, .height]
    container.addSubview(effectView)

    // Icon
    let imageView = NSImageView(frame: NSRect(x: 16, y: (height - 16) / 2, width: 16, height: 16))
    if let image = NSImage(systemSymbolName: icon, accessibilityDescription: nil) {
        let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .medium)
        imageView.image = image.withSymbolConfiguration(config)
    }
    imageView.contentTintColor = iconColor
    container.addSubview(imageView)

    // Label
    let textField = NSTextField(labelWithString: label)
    textField.font = .systemFont(ofSize: 13, weight: .medium)
    textField.textColor = .labelColor
    textField.sizeToFit()
    textField.frame.origin = NSPoint(x: 40, y: (height - textField.frame.height) / 2)
    container.addSubview(textField)

    // Dashed border for preview
    if dashed {
        let borderLayer = CAShapeLayer()
        borderLayer.path = NSBezierPath(roundedRect: container.bounds.insetBy(dx: 1, dy: 1), xRadius: height / 2, yRadius: height / 2).cgPath
        borderLayer.fillColor = nil
        borderLayer.strokeColor = NSColor.white.withAlphaComponent(0.3).cgColor
        borderLayer.lineWidth = 1.5
        borderLayer.lineDashPattern = [6, 4]
        container.layer?.addSublayer(borderLayer)
    }

    // Shadow
    container.shadow = NSShadow()
    container.layer?.shadowColor = NSColor.black.withAlphaComponent(0.25).cgColor
    container.layer?.shadowOffset = CGSize(width: 0, height: -2)
    container.layer?.shadowRadius = 6
    container.layer?.shadowOpacity = 1

    return container
}

private extension NSBezierPath {
    /// Convert NSBezierPath to CGPath.
    var cgPath: CGPath {
        let path = CGMutablePath()
        var points = [CGPoint](repeating: .zero, count: 3)
        for i in 0..<elementCount {
            let type = element(at: i, associatedPoints: &points)
            switch type {
            case .moveTo: path.move(to: points[0])
            case .lineTo: path.addLine(to: points[0])
            case .curveTo: path.addCurve(to: points[2], control1: points[0], control2: points[1])
            case .closePath: path.closeSubpath()
            case .cubicCurveTo: path.addCurve(to: points[2], control1: points[0], control2: points[1])
            case .quadraticCurveTo: path.addQuadCurve(to: points[1], control: points[0])
            @unknown default: break
            }
        }
        return path
    }
}

// MARK: - Toast Manager

/// Manages lightweight toast notification overlays.
final class ToastManager {
    static let shared = ToastManager()

    private var panel: NSPanel?
    private var previewPanel: NSPanel?
    private var dismissTimer: Timer?

    private static let panelWidth: CGFloat = 180
    private static let panelHeight: CGFloat = 44

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
            content = ("speaker.wave.2.fill", "Volume: \(value)%", .systemGreen)
        case "volume_down":
            content = ("speaker.wave.1.fill", "Volume: \(value)%", .systemRed)
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
        return NSPoint(
            x: visibleFrame.maxX - panelWidth - 20,
            y: visibleFrame.maxY - panelHeight - 10
        )
    }

    private func makePanel(at origin: NSPoint) -> NSPanel {
        let panel = NSPanel(
            contentRect: NSRect(x: origin.x, y: origin.y, width: Self.panelWidth, height: Self.panelHeight),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary]
        return panel
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
        panel = nil

        guard let screen = NSScreen.main else { return }

        let origin = Self.calculateOrigin(
            positionX: positionX,
            positionY: positionY,
            panelWidth: Self.panelWidth,
            panelHeight: Self.panelHeight,
            visibleFrame: screen.visibleFrame
        )

        let panel = makePanel(at: origin)
        panel.contentView = makeToastCapsule(
            icon: icon,
            label: label,
            iconColor: color,
            width: Self.panelWidth,
            height: Self.panelHeight
        )
        panel.orderFront(nil)
        self.panel = panel

        dismissTimer = Timer.scheduledTimer(withTimeInterval: Double(durationMs) / 1000, repeats: false) { [weak self] _ in
            self?.panel?.orderOut(nil)
            self?.panel = nil
        }
    }

    private func showPreviewPanel(positionX: Double?, positionY: Double?) {
        previewPanel?.orderOut(nil)
        previewPanel = nil

        guard let screen = NSScreen.main else { return }

        let origin = Self.calculateOrigin(
            positionX: positionX,
            positionY: positionY,
            panelWidth: Self.panelWidth,
            panelHeight: Self.panelHeight,
            visibleFrame: screen.visibleFrame
        )

        let panel = makePanel(at: origin)
        panel.contentView = makeToastCapsule(
            icon: "bell.fill",
            label: "Toast Preview",
            iconColor: .secondaryLabelColor,
            width: Self.panelWidth,
            height: Self.panelHeight,
            dashed: true,
            draggable: true
        )
        panel.orderFront(nil)
        self.previewPanel = panel
    }
}
