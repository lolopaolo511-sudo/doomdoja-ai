import Foundation
import SwiftData

@Model
final class Chat {
    @Attribute(.unique) var id: UUID
    var title: String
    var createdAt: Date
    var updatedAt: Date

    @Relationship(deleteRule: .cascade, inverse: \Message.chat)
    var messages: [Message]

    init(title: String = "New Chat") {
        self.id = UUID()
        self.title = title
        self.createdAt = Date()
        self.updatedAt = Date()
        self.messages = []
    }

    var lastMessagePreview: String {
        messages
            .sorted { $0.timestamp < $1.timestamp }
            .last?.content
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .prefix(80)
            .description ?? "No messages yet"
    }

    var sortedMessages: [Message] {
        messages.sorted { $0.timestamp < $1.timestamp }
    }
}
