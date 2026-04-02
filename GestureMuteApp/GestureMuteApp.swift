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
                .task {
                    appViewModel.bootstrap()
                }
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environment(appViewModel)
        }
    }
}
