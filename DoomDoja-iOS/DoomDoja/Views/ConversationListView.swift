import SwiftUI

struct ConversationListView: View {
    @Environment(ChatStore.self) private var store
    @Environment(AppSettings.self) private var settings
    @State private var searchText = ""
    @State private var showSettings = false
    @State private var chatToRename: Chat?
    @State private var renameTitle = ""

    var filtered: [Chat] {
        guard !searchText.isEmpty else { return store.chats }
        return store.chats.filter {
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            $0.lastMessagePreview.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationSplitView {
            Group {
                if store.chats.isEmpty {
                    emptyState
                } else {
                    List(selection: Binding(
                        get: { store.activeChat },
                        set: { if let c = $0 { store.selectChat(c) } }
                    )) {
                        ForEach(filtered) { chat in
                            ChatRowView(chat: chat)
                                .tag(chat)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        store.deleteChat(chat)
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                                .swipeActions(edge: .leading) {
                                    Button {
                                        chatToRename = chat
                                        renameTitle = chat.title
                                    } label: {
                                        Label("Rename", systemImage: "pencil")
                                    }
                                    .tint(.orange)
                                }
                        }
                    }
                    .searchable(text: $searchText, prompt: "Search conversations")
                }
            }
            .navigationTitle("DoomDoja")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { showSettings = true } label: {
                        Image(systemName: "gear")
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        let chat = store.createChat()
                        store.selectChat(chat)
                    } label: {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView()
            }
            .alert("Rename Chat", isPresented: Binding(
                get: { chatToRename != nil },
                set: { if !$0 { chatToRename = nil } }
            )) {
                TextField("Title", text: $renameTitle)
                Button("Rename") {
                    if let chat = chatToRename, !renameTitle.isEmpty {
                        store.renameChat(chat, title: renameTitle)
                    }
                    chatToRename = nil
                }
                Button("Cancel", role: .cancel) { chatToRename = nil }
            }
        } detail: {
            if let chat = store.activeChat {
                ChatView(chat: chat)
            } else {
                placeholderDetail
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 56))
                .foregroundStyle(.secondary)
            Text("No conversations yet")
                .font(.title3)
                .foregroundStyle(.secondary)
            Button("Start a new chat") {
                let chat = store.createChat()
                store.selectChat(chat)
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var placeholderDetail: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right.fill")
                .font(.system(size: 60))
                .foregroundStyle(.secondary)
            Text("Select a conversation")
                .font(.title2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct ChatRowView: View {
    let chat: Chat

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(chat.title)
                .font(.headline)
                .lineLimit(1)
            Text(chat.lastMessagePreview)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(.vertical, 4)
    }
}
