import SwiftUI

struct AdvancedSettingsView: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        Form {
            Section("Performance") {
                Toggle("Adaptive Frame Skip", isOn: adaptiveBinding)

                Stepper(
                    "Frame Skip: \(viewModel.config.frameSkip)",
                    value: frameSkipBinding,
                    in: 1...10
                )
                .disabled(viewModel.config.adaptiveFrameSkip)
            }

            Section("Gesture Detection") {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Two Fists Max Distance")
                            .font(.system(size: 13))
                        Spacer()
                        Text(String(format: "%.2f", viewModel.config.twoFistsMaxDistance))
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                    }
                    Slider(value: twoFistsBinding, in: 0.1...1.0, step: 0.05)
                }
            }

            Section {
                Button("Reset All Settings to Defaults") {
                    viewModel.config = AppConfig(onboardingCompleted: true)
                }
                .foregroundStyle(.red)
            }
        }
        .formStyle(.grouped)
    }

    private var frameSkipBinding: Binding<Int> {
        Binding(
            get: { viewModel.config.frameSkip },
            set: { newVal in
                var config = viewModel.config
                config.frameSkip = newVal
                viewModel.config = config
            }
        )
    }

    private var adaptiveBinding: Binding<Bool> {
        Binding(
            get: { viewModel.config.adaptiveFrameSkip },
            set: { newVal in
                var config = viewModel.config
                config.adaptiveFrameSkip = newVal
                viewModel.config = config
            }
        )
    }

    private var twoFistsBinding: Binding<Double> {
        Binding(
            get: { viewModel.config.twoFistsMaxDistance },
            set: { newVal in
                var config = viewModel.config
                config.twoFistsMaxDistance = newVal
                viewModel.config = config
            }
        )
    }
}
