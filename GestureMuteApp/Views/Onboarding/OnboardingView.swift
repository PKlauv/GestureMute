import SwiftUI

/// Two-step onboarding: Permissions → Camera Selection.
struct OnboardingView: View {
    @Environment(AppViewModel.self) private var viewModel
    @Environment(\.dismiss) private var dismiss
    @State private var currentStep = 0

    var body: some View {
        VStack(spacing: 0) {
            // Content
            Group {
                switch currentStep {
                case 0:
                    PermissionsStepView()
                case 1:
                    CameraSelectionStepView()
                default:
                    EmptyView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Step dots
            HStack(spacing: 6) {
                ForEach(0..<2, id: \.self) { step in
                    Circle()
                        .fill(step == currentStep ? Color.primary : Color.primary.opacity(0.2))
                        .frame(width: 6, height: 6)
                }
            }
            .padding(.bottom, 20)
        }
        .frame(width: 480, height: 560)
        .environment(viewModel)
        .onChange(of: currentStep) { _, newStep in
            if newStep == 1 {
                viewModel.refreshCameras()
            }
        }
    }

    /// Advance to next step or finish onboarding.
    func nextStep() {
        if currentStep < 1 {
            withAnimation {
                currentStep += 1
            }
        } else {
            finishOnboarding()
        }
    }

    func finishOnboarding() {
        var config = viewModel.config
        config.onboardingCompleted = true
        viewModel.config = config
        viewModel.startDetection()
        dismiss()

        // Schedule first gesture hint
        if !viewModel.shownGestureHints.contains("open_palm") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
                viewModel.pendingHint = .openPalm
            }
        }
    }
}
