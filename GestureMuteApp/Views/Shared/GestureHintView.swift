import SwiftUI

/// Contextual gesture hint shown near the menu bar.
struct GestureHintOverlay: View {
    @Environment(AppViewModel.self) private var viewModel

    var body: some View {
        if let hint = viewModel.pendingHint {
            HStack(alignment: .top, spacing: 10) {
                Text(hint.emoji)
                    .font(.system(size: 22))

                VStack(alignment: .leading, spacing: 2) {
                    Text(hint.title)
                        .font(.system(size: 13, weight: .medium))
                    Text(hint.subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineSpacing(2)
                }

                Spacer()
            }
            .padding(14)
            .frame(maxWidth: 260)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
            .overlay(alignment: .topTrailing) {
                Button {
                    viewModel.dismissHint(hint)
                } label: {
                    Text("Got it")
                        .font(.system(size: 11))
                        .foregroundStyle(.blue)
                }
                .buttonStyle(.plain)
                .padding(10)
            }
            .shadow(radius: 8)
            .transition(.opacity.combined(with: .move(edge: .top)))
        }
    }
}
