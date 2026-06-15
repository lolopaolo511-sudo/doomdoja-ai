import SwiftUI

struct ChatView: View {
    let chat: Chat
    @Environment(ChatStore.self) private var store
    @Environment(AppSettings.self) private var settings

    @State private var inputText = ""

    private var isActiveChat: Bool { store.activeChat?.id == chat.id }
    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.isStreaming
    }

    var body: some View {
        VStack(spacing: 0) {
            messageList

            if let err = store.errorMessage, isActiveChat {
                errorBanner(err)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            inputBar
        }
        .navigationTitle(chat.title)
        .navigationBarTitleDisplayMode(.inline)
        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: store.errorMessage != nil)
    }

    // MARK: - Message list

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(chat.sortedMessages) { message in
                        MessageView(message: message)
                            .id(message.id)
                            .environment(store)
                    }
                    Color.clear.frame(height: 8).id("bottom")
                }
                .padding(.vertical, 8)
                .animation(.spring(response: 0.35, dampingFraction: 0.8), value: chat.messages.count)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: chat.messages.count) { _, _ in
                scrollToBottom(proxy)
            }
            .onChange(of: store.streamingTokenCount) { _, _ in
                if store.isStreaming { scrollToBottom(proxy, animated: false) }
            }
            .onAppear { scrollToBottom(proxy, animated: false) }
        }
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy, animated: Bool = true) {
        if animated {
            withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom") }
        } else {
            proxy.scrollTo("bottom")
        }
    }

    // MARK: - Error banner

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.yellow)
                .font(.caption)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Spacer()
            Button { store.errorMessage = nil } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.tertiary)
                    .font(.subheadline)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .overlay(Divider(), alignment: .top)
    }

    // MARK: - Input bar

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message DoomDoja…", text: $inputText, axis: .vertical)
                .lineLimit(1...6)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                .disabled(store.isStreaming)
                .submitLabel(.send)
                .onSubmit {
                    if canSend { Task { await send() } }
                }

            sendButton
        }
        .padding(.horizontal, 12)
        .padding(.top, 10)
        .padding(.bottom, 24)
        .background(.ultraThinMaterial)
        .overlay(Divider(), alignment: .top)
    }

    private var sendButton: some View {
        Button {
            Task { await send() }
        } label: {
            ZStack {
                Circle()
                    .fill(canSend ? Color.accentColor : Color(.tertiarySystemFill))
                    .frame(width: 36, height: 36)
                Image(systemName: "arrow.up")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(canSend ? .white : Color(.tertiaryLabel))
            }
        }
        .disabled(!canSend)
        .animation(.spring(response: 0.25, dampingFraction: 0.7), value: canSend)
    }

    private func send() async {
        let text = inputText
        inputText = ""
        await store.sendMessage(content: text, in: chat, settings: settings)
    }
}
