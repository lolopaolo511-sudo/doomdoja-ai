import SwiftUI

struct ChatView: View {
    let chat: Chat
    @Environment(ChatStore.self) private var store
    @Environment(AppSettings.self) private var settings
    @State private var inputText = ""
    @FocusState private var inputFocused: Bool

    private var isActiveChat: Bool { store.activeChat?.id == chat.id }
    private var isStreamingHere: Bool { store.isStreaming && isActiveChat }
    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.isStreaming
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(chat.sortedMessages) { message in
                        MessageView(message: message)
                            .id(message.id)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    }

                    if isStreamingHere, chat.sortedMessages.last?.content.isEmpty != false {
                        TypingIndicatorView()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .id("typing")
                    }

                    Color.clear.frame(height: 1).id("bottom")
                }
                .padding(.vertical, 14)
            }
            .scrollDismissesKeyboard(.interactively)
            .defaultScrollAnchor(.bottom)
            .onChange(of: chat.sortedMessages.last?.content) { _, _ in
                withAnimation(.easeOut(duration: 0.18)) { proxy.scrollTo("bottom", anchor: .bottom) }
            }
            .onChange(of: chat.messages.count) { _, _ in
                withAnimation(.snappy) { proxy.scrollTo("bottom", anchor: .bottom) }
            }
            .onAppear { proxy.scrollTo("bottom", anchor: .bottom) }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: 0) {
                    if let error = store.errorMessage, isActiveChat {
                        ErrorBanner(message: error) { store.errorMessage = nil }
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                    inputBar
                }
            }
        }
        .navigationTitle(chat.title)
        .navigationBarTitleDisplayMode(.inline)
        .sensoryFeedback(.impact(weight: .light), trigger: chat.messages.count)
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message DoomDoja", text: $inputText, axis: .vertical)
                .lineLimit(1...6)
                .padding(.horizontal, 14)
                .padding(.vertical, 11)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: DoomTheme.bubbleRadius))
                .focused($inputFocused)
                .submitLabel(.send)
                .onSubmit { if canSend { Task { await send() } } }

            Button {
                Task { await send() }
            } label: {
                Image(systemName: isStreamingHere ? "ellipsis" : "arrow.up")
                    .font(.headline.weight(.bold))
                    .frame(width: 42, height: 42)
                    .foregroundStyle(.white)
                    .background(DoomTheme.accent, in: Circle())
                    .contentTransition(.symbolEffect(.replace))
            }
            .disabled(!canSend)
            .opacity(canSend ? 1 : 0.42)
            .accessibilityLabel(isStreamingHere ? "Waiting for response" : "Send message")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.bar)
    }

    private func send() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        await store.sendMessage(content: text, in: chat, settings: settings)
    }
}

private struct ErrorBanner: View {
    let message: String
    let dismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .lineLimit(3)
            Spacer()
            Button("Dismiss", systemImage: "xmark", action: dismiss)
                .labelStyle(.iconOnly)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.regularMaterial)
    }
}
