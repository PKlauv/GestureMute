import SwiftUI

/// Onboarding step 1: Check and request permissions.
struct PermissionsStepView: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Icon
            Image(systemName: "mic.fill")
                .font(.system(size: 32))
                .foregroundStyle(.secondary)
                .frame(width: 64, height: 64)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 16))
                .padding(.bottom, 16)

            Text("Welcome to GestureMute")
                .font(.system(size: 22, weight: .semibold))
                .padding(.bottom, 6)

            Text("Control your microphone with hand gestures.\nWe need a couple permissions to get started.")
                .font(.system(size: 13))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .lineSpacing(2)
                .padding(.bottom, 28)

            // Permissions list
            VStack(spacing: 8) {
                // Camera
                PermissionRow(
                    icon: "camera.fill",
                    iconColor: viewModel.permissions.cameraAuthorized ? .green : .blue,
                    title: "Camera Access",
                    subtitle: "Required — to see your hand gestures",
                    isGranted: viewModel.permissions.cameraAuthorized,
                    action: {
                        viewModel.permissions.requestCameraAccess { _ in }
                    },
                    actionLabel: "Grant Access"
                )

                // Accessibility
                PermissionRow(
                    icon: "lock.shield.fill",
                    iconColor: viewModel.permissions.accessibilityEnabled ? .green : .orange,
                    title: "Accessibility",
                    subtitle: "Optional — for ⌃⇧G keyboard shortcut",
                    isGranted: viewModel.permissions.accessibilityEnabled,
                    action: {
                        viewModel.permissions.openAccessibilitySettings()
                    },
                    actionLabel: "Open Settings"
                )
            }
            .padding(.horizontal, 40)

            Spacer()

            // Continue button
            Button {
                // Find the parent OnboardingView and call nextStep
                // We use a notification for simplicity
                NotificationCenter.default.post(name: .onboardingNextStep, object: nil)
            } label: {
                Text("Continue")
                    .font(.system(size: 14, weight: .medium))
                    .frame(maxWidth: 200)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!viewModel.permissions.cameraAuthorized)
            .padding(.bottom, 8)
        }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            // Re-check permissions when app regains focus
            viewModel.permissions.checkAll()
        }
    }
}

struct PermissionRow: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    let isGranted: Bool
    let action: () -> Void
    let actionLabel: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 15))
                .foregroundStyle(.white)
                .frame(width: 32, height: 32)
                .background(iconColor.opacity(0.8), in: RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                Text(subtitle)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if isGranted {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                    .font(.system(size: 16))
            } else {
                Button(actionLabel) {
                    action()
                }
                .font(.system(size: 11))
                .controlSize(.small)
            }
        }
        .padding(14)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
    }
}

extension Notification.Name {
    static let onboardingNextStep = Notification.Name("onboardingNextStep")
}
