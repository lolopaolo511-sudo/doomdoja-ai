import Foundation
import SwiftData

enum MessageRole: String, Codable {
    case user
    case assistant
    case system
}

@Model
final class Message {
    @Attribute(.unique) var id: UUID
    var roleRaw: String
    var content: String
    var timestamp: Date
    var chat: Chat?

    init(role: MessageRole, content: String, chat: Chat? = nil) {
        self.id = UUID()
        self.roleRaw = role.rawValue
        self.content = content
        self.timestamp = Date()
        self.chat = chat
    }

    var role: MessageRole {
        get { MessageRole(rawValue: roleRaw) ?? .user }
        set { roleRaw = newValue.rawValue }
    }

    var isUser: Bool { role == .user }
    var isAssistant: Bool { role == .assistant }

    // Converts to the dict format expected by OpenAI-compatible API
    var apiRepresentation: [String: String] {
        ["role": roleRaw, "content": content]
    }
}
