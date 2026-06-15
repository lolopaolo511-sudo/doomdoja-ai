import SwiftUI

enum DoomTheme {
    static let accent = Color(red: 0.48, green: 0.37, blue: 0.98)
    static let userBubble = Color(red: 0.38, green: 0.25, blue: 0.92)
    static let assistantBubble = Color(uiColor: .secondarySystemBackground)
    static let codeBackground = Color(uiColor: .systemGray6)
    static let bubbleRadius: CGFloat = 19
}

struct ConnectionBadge: View {
    let status: ChatStore.ConnectionStatus

    var body: some View {
        Label(label, systemImage: "circle.fill")
            .font(.caption.weight(.medium))
            .foregroundStyle(color)
            .accessibilityLabel("Server status: \(label)")
    }

    private var label: String {
        switch status {
        case .connected: "Connected"
        case .disconnected: "Offline"
        case .unknown: "Not tested"
        }
    }

    private var color: Color {
        switch status {
        case .connected: .green
        case .disconnected: .red
        case .unknown: .secondary
        }
    }
}
