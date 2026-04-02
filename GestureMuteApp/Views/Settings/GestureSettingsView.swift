import SwiftUI

struct GestureSettingsView: View {
    @Environment(AppViewModel.self) private var viewModel

    /// The configurable gestures (excludes NONE).
    private let gestures: [GestureType] = [
        .OPEN_PALM, .CLOSED_FIST, .THUMB_UP, .THUMB_DOWN, .TWO_FISTS_CLOSE,
    ]

    var body: some View {
        Form {
            Section {
                Text("Minimum confidence required to recognize each gesture")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)

                ForEach(gestures, id: \.self) { gesture in
                    GestureThresholdRow(gesture: gesture)
                }
            } header: {
                Text("Confidence Thresholds")
            }

            Section("Volume") {
                Stepper(
                    "Volume Step: \(viewModel.config.volumeStep)%",
                    value: volumeStepBinding,
                    in: 1...20
                )
            }
        }
        .formStyle(.grouped)
    }

    private var volumeStepBinding: Binding<Int> {
        Binding(
            get: { viewModel.config.volumeStep },
            set: { newVal in
                var config = viewModel.config
                config.volumeStep = newVal
                viewModel.config = config
            }
        )
    }
}

struct GestureThresholdRow: View {
    @Environment(AppViewModel.self) private var viewModel
    let gesture: GestureType

    private var threshold: Double {
        viewModel.config.confidenceThresholds[gesture.configKey] ?? 0.7
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(gesture.emoji)
                Text(gesture.displayName)
                    .font(.system(size: 13))
                Text("→ \(gesture.actionLabel)")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(Int(threshold * 100))%")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: thresholdBinding, in: 0.3...0.95, step: 0.05)
        }
    }

    private var thresholdBinding: Binding<Double> {
        Binding(
            get: { threshold },
            set: { newVal in
                var config = viewModel.config
                config.confidenceThresholds[gesture.configKey] = newVal
                viewModel.config = config
            }
        )
    }
}
