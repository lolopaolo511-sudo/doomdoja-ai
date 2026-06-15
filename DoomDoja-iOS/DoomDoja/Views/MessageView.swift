import SwiftUI

struct MessageView: View {
    let message: Message
    @Environment(ChatStore.self) private var store

    private var isStreamingThisMessage: Bool {
        store.isStreaming && message.isAssistant
            && store.activeChat?.sortedMessages.last?.id == message.id
    }

    var body: some View {
        Group {
            if message.isUser {
                HStack(alignment: .top, spacing: 0) {
                    Spacer(minLength: 60)
                    userBubble.padding(.trailing, 14)
                }
            } else {
                HStack(alignment: .top, spacing: 10) {
                    avatarView
                    assistantContent
                    Spacer(minLength: 40)
                }
                .padding(.leading, 14)
            }
        }
        .padding(.vertical, 4)
        .transition(.asymmetric(
            insertion: .move(edge: .bottom).combined(with: .opacity),
            removal: .opacity
        ))
    }

    // MARK: - User bubble

    private var userBubble: some View {
        Text(message.content)
            .foregroundStyle(.white)
            .textSelection(.enabled)
            .padding(.horizontal, 15)
            .padding(.vertical, 11)
            .background(
                LinearGradient(
                    colors: [Color.accentColor, Color.accentColor.opacity(0.82)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .contextMenu {
                Button { UIPasteboard.general.string = message.content } label: {
                    Label("Copy", systemImage: "doc.on.doc")
                }
            }
    }

    // MARK: - Assistant content

    private var assistantContent: some View {
        VStack(alignment: .leading, spacing: 6) {
            if message.content.isEmpty {
                TypingIndicatorView()
            } else {
                MarkdownContentView(text: message.content)
                if isStreamingThisMessage {
                    StreamingCursorView()
                }
            }
        }
        .contextMenu {
            if !message.content.isEmpty {
                Button { UIPasteboard.general.string = message.content } label: {
                    Label("Copy", systemImage: "doc.on.doc")
                }
            }
        }
    }

    // MARK: - Avatar

    private var avatarView: some View {
        ZStack {
            Circle()
                .fill(Color.accentColor.opacity(0.13))
                .frame(width: 28, height: 28)
            Text("D")
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(Color.accentColor)
        }
        .padding(.top, 2)
    }
}

// MARK: - Typing indicator

struct TypingIndicatorView: View {
    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3, id: \.self) { i in
                BouncingDot(index: i)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }
}

private struct BouncingDot: View {
    let index: Int
    @State private var isUp = false

    var body: some View {
        Circle()
            .fill(Color.secondary.opacity(0.55))
            .frame(width: 7, height: 7)
            .offset(y: isUp ? -5 : 0)
            .animation(
                .easeInOut(duration: 0.45)
                    .repeatForever(autoreverses: true)
                    .delay(Double(index) * 0.12),
                value: isUp
            )
            .onAppear { isUp = true }
    }
}

// MARK: - Streaming cursor

struct StreamingCursorView: View {
    @State private var visible = true

    var body: some View {
        Text("▋")
            .font(.body)
            .foregroundStyle(Color.accentColor)
            .opacity(visible ? 1 : 0)
            .animation(.easeInOut(duration: 0.5).repeatForever(), value: visible)
            .onAppear { visible = false }
    }
}
