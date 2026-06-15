import SwiftUI

struct ConversationListView: View {
    @Environment(ChatStore.self) private var store
    @State private var searchText = ""
    @State private var showSettings = false
    @State private var chatToRename: Chat?
    @State private var renameTitle = ""

    private var filteredChats: [Chat] {
        guard !searchText.isEmpty else { return store.chats }
        return store.chats.filter {
            $0.title.localizedStandardContains(searchText)
                || $0.lastMessagePreview.localizedStandardContains(searchText)
        }
    }

    var body: some View {
        NavigationSplitView {
            Group {
                if store.chats.isEmpty {
                    emptyState
                } else if filteredChats.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    List(selection: activeChatBinding) {
                        ForEach(filteredChats) { chat in
                            ChatRowView(chat: chat)
                                .tag(chat)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        withAnimation(.snappy) { store.deleteChat(chat) }
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                    Button {
                                        beginRename(chat)
                                    } label: {
                                        Label("Rename", systemImage: "pencil")
                                    }
                                    .tint(DoomTheme.accent)
                                }
                                .contextMenu {
                                    Button("Rename", systemImage: "pencil") { beginRename(chat) }
                                    Button("Delete", systemImage: "trash", role: .destructive) {
                                        withAnimation(.snappy) { store.deleteChat(chat) }
                                    }
                                }
                        }
                    }
                    .listStyle(.plain)
                    .refreshable { store.loadChats() }
                    .searchable(text: $searchText, prompt: "Search conversations")
                }
            }
            .navigationTitle("DoomDoja")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showSettings = true } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: createChat) {
                        Label("New conversation", systemImage: "square.and.pencil")
                    }
                }
            }
            .sheet(isPresented: $showSettings) { SettingsView() }
            .alert("Rename conversation", isPresented: renamePresented) {
                TextField("Conversation title", text: $renameTitle)
                Button("Cancel", role: .cancel) { chatToRename = nil }
                Button("Rename") {
                    guard let chatToRename else { return }
                    let title = renameTitle.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !title.isEmpty { store.renameChat(chatToRename, title: title) }
                    self.chatToRename = nil
                }
            }
        } detail: {
            if let chat = store.activeChat {
                ChatView(chat: chat)
            } else {
                ContentUnavailableView {
                    Label("Select a conversation", systemImage: "bubble.left.and.bubble.right")
                } description: {
                    Text("Choose an existing chat or start a new one.")
                } actions: {
                    Button("New conversation", action: createChat)
                        .buttonStyle(.borderedProminent)
                        .tint(DoomTheme.accent)
                }
            }
        }
        .tint(DoomTheme.accent)
    }

    private var activeChatBinding: Binding<Chat?> {
        Binding(
            get: { store.activeChat },
            set: { if let chat = $0 { store.selectChat(chat) } }
        )
    }

    private var renamePresented: Binding<Bool> {
        Binding(get: { chatToRename != nil }, set: { if !$0 { chatToRename = nil } })
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("Start a conversation", systemImage: "sparkles")
        } description: {
            Text("Your private conversations with DoomDoja will appear here.")
        } actions: {
            Button("New conversation", action: createChat)
                .buttonStyle(.borderedProminent)
                .tint(DoomTheme.accent)
        }
    }

    private func createChat() {
        withAnimation(.snappy) {
            let chat = store.createChat()
            store.selectChat(chat)
        }
    }

    private func beginRename(_ chat: Chat) {
        chatToRename = chat
        renameTitle = chat.title
    }
}

private struct ChatRowView: View {
    let chat: Chat

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "bubble.left.fill")
                .font(.subheadline)
                .foregroundStyle(DoomTheme.accent)
                .frame(width: 34, height: 34)
                .background(DoomTheme.accent.opacity(0.11), in: Circle())
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 5) {
                HStack {
                    Text(chat.title)
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                    Text(chat.updatedAt, format: .relative(presentation: .named))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
                Text(chat.lastMessagePreview)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 8)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}
