import SwiftUI

@main
struct GestureMuteApp: App {
    @State private var appViewModel = AppViewModel()

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environment(appViewModel)
        } label: {
            Image(systemName: appViewModel.menuBarIconName)
                .renderingMode(.template)
                .opacity(appViewModel.menuBarIconOpacity)
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environment(appViewModel)
        }

        Window("Welcome to GestureMute", id: "onboarding") {
            OnboardingView()
                .environment(appViewModel)
        }
        .windowResizability(.contentSize)
        .defaultSize(width: 480, height: 560)
        .windowStyle(.hiddenTitleBar)
    }

    init() {
        // Launch engine on startup
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [appViewModel] in
            appViewModel.launchEngine()

            // Auto-start detection if onboarding is complete
            if appViewModel.configManager.config.onboardingCompleted {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    appViewModel.startDetection()
                }
            }
        }
    }
}
