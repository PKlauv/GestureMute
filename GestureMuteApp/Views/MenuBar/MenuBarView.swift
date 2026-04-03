import SwiftUI

/// Menu bar popover content — quick status and controls.
struct MenuBarView: View {
    @Environment(AppViewModel.self) private var viewModel
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        VStack(spacing: 0) {
            // Status Header
            StatusHeaderView()
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

            Divider()

            // Detection Toggle
            HStack {
                Text("Detection")
                    .font(.system(size: 13))
                Spacer()
                Toggle("", isOn: Binding(
                    get: { viewModel.detectionActive },
                    set: { _ in viewModel.toggleDetection() }
                ))
                .toggleStyle(.switch)
                .labelsHidden()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            // Last Gesture
            HStack {
                Text("Last gesture")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                Spacer()
                if let gesture = viewModel.lastGesture, gesture != .NONE {
                    HStack(spacing: 4) {
                        Text(gesture.emoji)
                        Text("\(gesture.displayName)")
                            .font(.system(size: 12))
                        Text("\(Int(viewModel.lastConfidence * 100))%")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text("None")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            // Input Volume
            HStack {
                Text("Input Volume")
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                Spacer()
                if viewModel.micState == .MUTED || viewModel.micState == .LOCKED_MUTE {
                    Text("0% (muted)")
                        .font(.system(size: 12))
                        .foregroundStyle(.red)
                } else {
                    Text("\(viewModel.inputVolume)%")
                        .font(.system(size: 12))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            // Footer
            HStack {
                Button {
                    openSettings()
                    NSApp.activate(ignoringOtherApps: true)
                } label: {
                    Text("Settings...")
                        .font(.system(size: 12))
                        .foregroundStyle(.blue)
                }
                .buttonStyle(.plain)
                .modifier(HoverHighlight())

                Spacer()

                Button("Quit") {
                    viewModel.quit()
                }
                .buttonStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(.red)
                .modifier(HoverHighlight())
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .frame(width: 280)
    }
}

/// Hover highlight for interactive menu bar elements.
private struct HoverHighlight: ViewModifier {
    @State private var isHovered = false

    func body(content: Content) -> some View {
        content
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                isHovered ? Color.primary.opacity(0.1) : Color.clear,
                in: RoundedRectangle(cornerRadius: 6)
            )
            .onHover { isHovered = $0 }
    }
}

/// Status header showing mic state icon, label, and camera name.
struct StatusHeaderView: View {
    @Environment(AppViewModel.self) private var viewModel

    private var statusColor: Color {
        guard viewModel.detectionActive else { return .gray }
        switch viewModel.micState {
        case .LIVE: return .green
        case .MUTED: return .red
        case .LOCKED_MUTE: return .orange
        }
    }

    private var statusIcon: String {
        guard viewModel.detectionActive else { return "mic.fill" }
        switch viewModel.micState {
        case .LIVE: return "mic.fill"
        case .MUTED: return "mic.slash.fill"
        case .LOCKED_MUTE: return "lock.fill"
        }
    }

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: statusIcon)
                .font(.system(size: 16))
                .foregroundStyle(.white)
                .frame(width: 32, height: 32)
                .background(statusColor, in: RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 2) {
                Text(viewModel.detectionActive ? viewModel.micState.displayName : "Detection Paused")
                    .font(.system(size: 14, weight: .semibold))
                if let camera = viewModel.cameraName {
                    Text(camera)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()
        }
    }
}
