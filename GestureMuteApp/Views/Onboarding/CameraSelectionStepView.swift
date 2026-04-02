import SwiftUI

/// Onboarding step 2: Choose a camera.
struct CameraSelectionStepView: View {
    @Environment(AppViewModel.self) private var viewModel
    @State private var selectedCameraId: String = ""

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Icon
            Image(systemName: "camera.fill")
                .font(.system(size: 32))
                .foregroundStyle(.secondary)
                .frame(width: 64, height: 64)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 16))
                .padding(.bottom, 16)

            Text("Select Your Camera")
                .font(.system(size: 22, weight: .semibold))
                .padding(.bottom, 6)

            Text("Choose which camera to use for gesture detection.")
                .font(.system(size: 13))
                .foregroundStyle(.secondary)
                .padding(.bottom, 24)

            // Camera list
            VStack(spacing: 6) {
                if viewModel.availableCameras.isEmpty {
                    HStack {
                        ProgressView()
                            .controlSize(.small)
                        Text("Scanning for cameras...")
                            .font(.system(size: 13))
                            .foregroundStyle(.secondary)
                    }
                    .padding(14)
                } else {
                    ForEach(viewModel.availableCameras) { camera in
                        CameraRow(
                            camera: camera,
                            isSelected: selectedCameraId == camera.uniqueId,
                            onSelect: { selectedCameraId = camera.uniqueId }
                        )
                    }
                }
            }
            .padding(.horizontal, 40)

            Spacer()

            // Get Started button
            Button {
                applySelection()
                NotificationCenter.default.post(name: .onboardingNextStep, object: nil)
            } label: {
                Text("Get Started")
                    .font(.system(size: 14, weight: .medium))
                    .frame(maxWidth: 200)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(selectedCameraId.isEmpty && viewModel.availableCameras.isEmpty)
            .padding(.bottom, 8)
        }
        .onAppear {
            // Pre-select the first camera (built-in preferred)
            if let builtin = viewModel.availableCameras.first(where: { $0.isBuiltin }) {
                selectedCameraId = builtin.uniqueId
            } else if let first = viewModel.availableCameras.first {
                selectedCameraId = first.uniqueId
            }
        }
        .onChange(of: viewModel.availableCameras) { _, cameras in
            if selectedCameraId.isEmpty {
                if let builtin = cameras.first(where: { $0.isBuiltin }) {
                    selectedCameraId = builtin.uniqueId
                } else if let first = cameras.first {
                    selectedCameraId = first.uniqueId
                }
            }
        }
    }

    private func applySelection() {
        guard let camera = viewModel.availableCameras.first(where: { $0.uniqueId == selectedCameraId }) else { return }
        var config = viewModel.config
        config.cameraUniqueId = camera.uniqueId
        config.cameraName = camera.name
        config.cameraIndex = camera.index
        viewModel.config = config
    }
}

struct CameraRow: View {
    let camera: CameraInfo
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button {
            onSelect()
        } label: {
            HStack(spacing: 12) {
                Circle()
                    .fill(isSelected ? Color.accentColor : Color.clear)
                    .stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.3), lineWidth: 1.5)
                    .frame(width: 8, height: 8)

                VStack(alignment: .leading, spacing: 1) {
                    Text(camera.name)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.primary)
                    Text(camera.isBuiltin ? "Built-in" : "External")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark")
                        .foregroundStyle(Color.accentColor)
                        .font(.system(size: 14))
                }
            }
            .padding(12)
            .background(
                isSelected ? Color.accentColor.opacity(0.08) : Color.clear,
                in: RoundedRectangle(cornerRadius: 10)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isSelected ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}
