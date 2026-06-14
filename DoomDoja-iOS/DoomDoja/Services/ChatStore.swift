import Foundation
import SwiftData
import Observation

@Observable
final class ChatStore {

    // MARK: - Public state (Codex reads these)

    var chats: [Chat] = []
    var activeChat: Chat?
    var isStreaming: Bool = false
    var errorMessage: String?
    var connectionStatus: ConnectionStatus = .unknown

    enum ConnectionStatus {
        case unknown, connected, disconnected
    }

    // MARK: - Private

    private let api = APIService()
    private var modelContext: ModelContext

    init(modelContext: ModelContext) {
        self.modelContext = modelContext
        loadChats()
    }

    // MARK: - Chat CRUD

    func loadChats() {
        let descriptor = FetchDescriptor<Chat>(
            sortBy: [SortDescriptor(\.updatedAt, order: .reverse)]
        )
        chats = (try? modelContext.fetch(descriptor)) ?? []
    }

    @discardableResult
    func createChat(title: String = "New Chat") -> Chat {
        let chat = Chat(title: title)
        modelContext.insert(chat)
        save()
        loadChats()
        return chat
    }

    func deleteChat(_ chat: Chat) {
        if activeChat?.id == chat.id { activeChat = nil }
        modelContext.delete(chat)
        save()
        loadChats()
    }

    func renameChat(_ chat: Chat, title: String) {
        chat.title = title
        chat.updatedAt = Date()
        save()
        loadChats()
    }

    func selectChat(_ chat: Chat) {
        activeChat = chat
    }

    // MARK: - Messaging

    /// Adds a user message and streams the assistant reply.
    func sendMessage(content: String, in chat: Chat, settings: AppSettings) async {
        guard !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        guard let baseURL = settings.baseURL else {
            errorMessage = "Invalid server URL. Please check Settings."
            return
        }

        errorMessage = nil

        // 1. Persist user message
        let userMsg = Message(role: .user, content: content, chat: chat)
        chat.messages.append(userMsg)
        modelContext.insert(userMsg)
        chat.updatedAt = Date()
        save()

        // 2. Auto-title: first message becomes the chat title
        if chat.title == "New Chat", chat.messages.count == 1 {
            let preview = String(content.prefix(40))
            chat.title = preview
        }

        // 3. Placeholder assistant message
        let assistantMsg = Message(role: .assistant, content: "", chat: chat)
        chat.messages.append(assistantMsg)
        modelContext.insert(assistantMsg)
        loadChats()

        // 4. Stream
        isStreaming = true
        defer {
            isStreaming = false
            save()
            loadChats()
        }

        do {
            let stream = api.sendMessageStream(
                messages: chat.sortedMessages.filter { !$0.content.isEmpty || $0.isUser },
                model: settings.modelName,
                baseURL: baseURL,
                apiKey: settings.apiKey.isEmpty ? nil : settings.apiKey
            )

            for try await token in stream {
                assistantMsg.content += token
            }

            connectionStatus = .connected
        } catch {
            connectionStatus = .disconnected
            errorMessage = error.localizedDescription
            // Remove empty placeholder on failure
            if assistantMsg.content.isEmpty {
                modelContext.delete(assistantMsg)
                chat.messages.removeAll { $0.id == assistantMsg.id }
            }
        }

        chat.updatedAt = Date()
    }

    // MARK: - Connection test

    func testConnection(settings: AppSettings) async {
        guard let url = settings.baseURL else {
            connectionStatus = .disconnected
            return
        }
        let result = await api.testConnection(
            baseURL: url,
            apiKey: settings.apiKey.isEmpty ? nil : settings.apiKey
        )
        connectionStatus = result == nil ? .connected : .disconnected
        // Use pattern matching instead
        switch result {
        case .success: connectionStatus = .connected
        case .failure: connectionStatus = .disconnected
        }
    }

    func deleteMessage(_ message: Message, from chat: Chat) {
        chat.messages.removeAll { $0.id == message.id }
        modelContext.delete(message)
        save()
    }

    // MARK: - Persistence

    private func save() {
        try? modelContext.save()
    }
}
