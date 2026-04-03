import SwiftUI

struct GeneralSettingsView: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        @Bindable var vm = viewModel

        Form {
            Section("Camera") {
                Picker("Camera", selection: cameraBinding) {
                    // Placeholder tag for when no camera is selected yet
                    Text(viewModel.cameraName ?? "No cameras")
                        .tag("")
                    ForEach(viewModel.availableCameras) { camera in
                        Text(camera.name).tag(camera.uniqueId)
                    }
                }
                .onAppear {
                    viewModel.refreshCameras()
                }

                Button("Refresh Cameras") {
                    viewModel.refreshCameras()
                }
                .font(.system(size: 12))
            }

            Section("Feedback") {
                Toggle("Sound Cues", isOn: soundCuesBinding)
                Toggle("Toast Notifications", isOn: toastEnabledBinding)

                HStack {
                    Text("Toast Duration")
                    Spacer()
                    Text("\(String(format: "%.1f", Double(viewModel.config.toastDurationMs) / 1000))s")
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
                Slider(
                    value: toastDurationBinding,
                    in: 500...5000,
                    step: 100
                )
                .disabled(!viewModel.config.toastEnabled)
            }

            Section("Keyboard") {
                HStack {
                    Text("Toggle Detection")
                    Spacer()
                    HStack(spacing: 2) {
                        KeyCapView("⌃")
                        KeyCapView("⇧")
                        KeyCapView("G")
                    }
                }
            }
        }
        .formStyle(.grouped)
    }

    private var cameraBinding: Binding<String> {
        Binding(
            get: { viewModel.config.cameraUniqueId ?? "" },
            set: { newId in
                if let camera = viewModel.availableCameras.first(where: { $0.uniqueId == newId }) {
                    var config = viewModel.config
                    config.cameraUniqueId = camera.uniqueId
                    config.cameraName = camera.name
                    config.cameraIndex = camera.index
                    viewModel.config = config
                }
            }
        )
    }

    private var soundCuesBinding: Binding<Bool> {
        Binding(
            get: { viewModel.config.soundCuesEnabled },
            set: { newVal in
                var config = viewModel.config
                config.soundCuesEnabled = newVal
                viewModel.config = config
            }
        )
    }

    private var toastEnabledBinding: Binding<Bool> {
        Binding(
            get: { viewModel.config.toastEnabled },
            set: { newVal in
                var config = viewModel.config
                config.toastEnabled = newVal
                viewModel.config = config
            }
        )
    }

    private var toastDurationBinding: Binding<Double> {
        Binding(
            get: { Double(viewModel.config.toastDurationMs) },
            set: { newVal in
                var config = viewModel.config
                config.toastDurationMs = Int(newVal)
                viewModel.config = config
            }
        )
    }
}

/// Small key cap badge for displaying keyboard shortcuts.
struct KeyCapView: View {
    let key: String

    init(_ key: String) {
        self.key = key
    }

    var body: some View {
        Text(key)
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.quaternary, in: RoundedRectangle(cornerRadius: 4))
    }
}
