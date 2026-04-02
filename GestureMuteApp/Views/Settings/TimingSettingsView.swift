import SwiftUI

struct TimingSettingsView: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        Form {
            Section("Detection Timing") {
                TimingSlider(
                    label: "Gesture Cooldown",
                    value: binding(\.gestureCooldownMs),
                    range: 200...2000,
                    step: 50,
                    unit: "ms"
                )

                TimingSlider(
                    label: "Activation Delay",
                    value: binding(\.activationDelayMs),
                    range: 100...1000,
                    step: 50,
                    unit: "ms"
                )

                TimingSlider(
                    label: "No-Hand Timeout",
                    value: binding(\.noHandTimeoutMs),
                    range: 1000...10000,
                    step: 500,
                    unit: "ms"
                )

                TimingSlider(
                    label: "Grace Period",
                    value: binding(\.transitionGraceMs),
                    range: 100...1000,
                    step: 50,
                    unit: "ms"
                )

                TimingSlider(
                    label: "Volume Repeat Rate",
                    value: binding(\.volumeRepeatMs),
                    range: 100...2000,
                    step: 50,
                    unit: "ms"
                )
            }
        }
        .formStyle(.grouped)
    }

    private func binding(_ keyPath: WritableKeyPath<AppConfig, Int>) -> Binding<Double> {
        Binding(
            get: { Double(viewModel.config[keyPath: keyPath]) },
            set: { newVal in
                var config = viewModel.config
                config[keyPath: keyPath] = Int(newVal)
                viewModel.config = config
            }
        )
    }
}

struct TimingSlider: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let unit: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.system(size: 13))
                Spacer()
                Text("\(Int(value))\(unit)")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
            Slider(value: $value, in: range, step: step)
        }
    }
}
