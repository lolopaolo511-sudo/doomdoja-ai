import SwiftUI

struct ConversationListView: View {
    @Environment(ChatStore.self) private var store
    @Environment(AppSettings.self) private var settings
    @State private var searchText = ""
    @State private var showSettings = false
    @State private var chatToRename: Chat?
    @State private var renameTitle = ""

    private var filtered: [Chat] {
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
                    chatList
                }
            }
            .navigationTitle("DoomDoja")
            .searchable(text: $searchText, prompt: "Search conversations")
            .toolbar { toolbarContent }
            .sheet(isPresented: $showSettings) {
                SettingsView()
                    .environment(store)
                    .environment(settings)
            }
            .alert("Rename", isPresented: Binding(
                get: { chatToRename != nil },
                set: { if !$0 { chatToRename = nil } }
            )) {
                TextField("Chat title", text: $renameTitle)
                Button("Rename") {
                    if let c = chatToRename, !renameTitle.isEmpty {
                        store.renameChat(c, title: renameTitle)
                    }
                    chatToRename = nil
                }
                Button("Cancel", role: .cancel) { chatToRename = nil }
            }
        } detail: {
            if let chat = store.activeChat {
                ChatView(chat: chat)
                    .environment(store)
                    .environment(settings)
            } else {
                placeholderDetail
            }
        }
    }

    // MARK: - Chat list

    private var chatList: some View {
        List(selection: Binding(
            get: { store.activeChat },
            set: { if let c = $0 { store.selectChat(c) } }
        )) {
            ForEach(filtered) { chat in
                ChatRowView(chat: chat)
                    .tag(chat)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            withAnimation { store.deleteChat(chat) }
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
                    .listRowSeparator(.hidden)
                    .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
            }
        }
        .listStyle(.plain)
        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: store.chats.map(\.id))
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigationBarLeading) {
            Button {
                showSettings = true
            } label: {
                Image(systemName: "gear")
                    .symbolRenderingMode(.hierarchical)
            }
        }
        ToolbarItem(placement: .navigationBarTrailing) {
            Button {
                let chat = store.createChat()
                store.selectChat(chat)
            } label: {
                Image(systemName: "square.and.pencil")
                    .symbolRenderingMode(.hierarchical)
            }
        }
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: 20) {
            ZStack {
                Circle()
                    .fill(Color.accentColor.opacity(0.1))
                    .frame(width: 90, height: 90)
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.system(size: 38, weight: .semibold))
                    .foregroundStyle(Color.accentColor.opacity(0.7))
            }
            VStack(spacing: 8) {
                Text("No conversations yet")
                    .font(.title3.weight(.semibold))
                Text("Start a new chat to talk with DoomDoja.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            Button {
                let chat = store.createChat()
                store.selectChat(chat)
            } label: {
                Label("New Chat", systemImage: "plus")
                    .font(.headline)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .buttonBorderShape(.capsule)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.horizontal, 40)
    }

    // MARK: - Placeholder detail

    private var placeholderDetail: some View {
        VStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(Color.accentColor.opacity(0.08))
                    .frame(width: 80, height: 80)
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(Color.accentColor.opacity(0.5))
            }
            Text("Select a conversation")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Chat row

private struct ChatRowView: View {
    let chat: Chat

    var body: some View {
        HStack(spacing: 12) {
            avatarView
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(chat.title)
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                    Text(relativeTime)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                Text(chat.lastMessagePreview)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.vertical, 6)
    }

    private var avatarView: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(avatarColor.opacity(0.15))
                .frame(width: 44, height: 44)
            Text(String(chat.title.prefix(1)).uppercased())
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(avatarColor)
        }
    }

    private var avatarColor: Color {
        let palette: [Color] = [.blue, .purple, .indigo, .teal, .orange, .pink, .green, .cyan]
        return palette[abs(chat.id.hashValue) % palette.count]
    }

    private var relativeTime: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: chat.updatedAt, relativeTo: Date())
    }
}
