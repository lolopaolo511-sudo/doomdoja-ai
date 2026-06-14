import SwiftUI

struct ChatView: View {
    let chat: Chat
    @Environment(ChatStore.self) private var store
    @Environment(AppSettings.self) private var settings

    @State private var inputText = ""
    @State private var scrollProxy: ScrollViewProxy?
    @State private var showError = false

    private var isActiveChat: Bool { store.activeChat?.id == chat.id }
    private var canSend: Bool { !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.isStreaming }

    var body: some View {
        VStack(spacing: 0) {
            // Message list
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(chat.sortedMessages) { message in
                            MessageView(message: message)
                                .id(message.id)
                        }

                        if store.isStreaming && isActiveChat {
                            let last = chat.sortedMessages.last
                            if last?.isUser == true {
                                HStack {
                                    TypingIndicatorView()
                                    Spacer()
                                }
                            }
                        }

                        // Scroll anchor
                        Color.clear
                            .frame(height: 1)
                            .id("bottom")
                    }
                    .padding(.vertical, 8)
                }
                .onChange(of: chat.messages.count) { _, _ in
                    withAnimation { proxy.scrollTo("bottom") }
                }
                .onChange(of: store.isStreaming) { _, streaming in
                    if streaming { withAnimation { proxy.scrollTo("bottom") } }
                }
                .onAppear {
                    proxy.scrollTo("bottom")
                }
            }

            Divider()

            // Error banner
            if let err = store.errorMessage, isActiveChat {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.yellow)
                    Text(err)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button { store.errorMessage = nil } label: {
                        Image(systemName: "xmark")
                            .font(.caption)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color(.tertiarySystemBackground))
            }

            // Input bar
            inputBar
        }
        .navigationTitle(chat.title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message DoomDoja…", text: $inputText, axis: .vertical)
                .lineLimit(1...6)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 22))
                .disabled(store.isStreaming)

            Button {
                Task { await send() }
            } label: {
                Image(systemName: store.isStreaming ? "stop.circle.fill" : "arrow.up.circle.fill")
                    .font(.system(size: 34))
                    .foregroundStyle(canSend ? Color.accentColor : .secondary)
            }
            .disabled(!canSend && !store.isStreaming)
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 16)
        .background(.ultraThinMaterial)
    }

    private func send() async {
        let text = inputText
        inputText = ""
        await store.sendMessage(content: text, in: chat, settings: settings)
    }
}
