import SwiftUI

/// Main settings window with sidebar navigation.
struct SettingsView: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gearshape")
                }

            GestureSettingsView()
                .tabItem {
                    Label("Gestures", systemImage: "hand.raised")
                }

            TimingSettingsView()
                .tabItem {
                    Label("Timing", systemImage: "timer")
                }

            AdvancedSettingsView()
                .tabItem {
                    Label("Advanced", systemImage: "wrench.and.screwdriver")
                }
        }
        .environment(viewModel)
        .frame(width: 500, height: 420)
    }
}
