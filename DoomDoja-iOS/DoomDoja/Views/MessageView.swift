import SwiftUI
import UIKit

struct MessageView: View {
    let message: Message

    var body: some View {
        HStack(alignment: .bottom, spacing: 10) {
            if message.isUser { Spacer(minLength: 44) }

            if message.isAssistant {
                Image(systemName: "sparkles")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(DoomTheme.accent)
                    .frame(width: 28, height: 28)
                    .background(DoomTheme.accent.opacity(0.12), in: Circle())
                    .accessibilityHidden(true)
            }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 5) {
                MessageContentView(content: message.content, isUser: message.isUser)
                    .padding(.horizontal, message.isUser ? 15 : 0)
                    .padding(.vertical, message.isUser ? 11 : 0)
                    .foregroundStyle(message.isUser ? .white : .primary)
                    .background(message.isUser ? DoomTheme.userBubble : .clear)
                    .clipShape(RoundedRectangle(cornerRadius: DoomTheme.bubbleRadius, style: .continuous))
                    .contextMenu {
                        Button("Copy", systemImage: "doc.on.doc") {
                            UIPasteboard.general.string = message.content
                        }
                    }

                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .padding(.horizontal, 4)
            }

            if !message.isUser { Spacer(minLength: 26) }
        }
        .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message.isUser ? "You" : "DoomDoja"): \(message.content)")
    }
}

private struct MessageContentView: View {
    let content: String
    let isUser: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(Array(MarkdownBlockParser.parse(content).enumerated()), id: \.offset) { _, block in
                switch block {
                case .text(let text):
                    markdownText(text)
                case .code(let language, let code):
                    CodeBlockView(language: language, code: code)
                }
            }
        }
        .textSelection(.enabled)
        .animation(.easeOut(duration: 0.12), value: content)
    }

    @ViewBuilder
    private func markdownText(_ text: String) -> some View {
        if let attributed = try? AttributedString(
            markdown: text,
            options: .init(interpretedSyntax: .full)
        ) {
            Text(attributed)
                .font(.body)
                .lineSpacing(3)
        } else {
            Text(text)
                .font(.body)
        }
    }
}

private struct CodeBlockView: View {
    let language: String?
    let code: String
    @State private var copied = false

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Text(language?.isEmpty == false ? language! : "code")
                    .font(.caption.monospaced().weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    UIPasteboard.general.string = code
                    copied = true
                    Task {
                        try? await Task.sleep(for: .seconds(1.5))
                        copied = false
                    }
                } label: {
                    Label(copied ? "Copied" : "Copy", systemImage: copied ? "checkmark" : "doc.on.doc")
                        .contentTransition(.symbolEffect(.replace))
                }
                .font(.caption)
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 9)

            Divider()

            ScrollView(.horizontal) {
                Text(SyntaxHighlighter.highlight(code, language: language))
                    .font(.system(.callout, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(12)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(DoomTheme.codeBackground, in: RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Color(uiColor: .separator).opacity(0.4), lineWidth: 0.5)
        }
    }
}

private enum MarkdownBlock: Equatable {
    case text(String)
    case code(language: String?, content: String)
}

private enum MarkdownBlockParser {
    static func parse(_ source: String) -> [MarkdownBlock] {
        let lines = source.components(separatedBy: .newlines)
        var blocks: [MarkdownBlock] = []
        var textLines: [String] = []
        var codeLines: [String] = []
        var language: String?
        var inCode = false

        func flushText() {
            guard !textLines.isEmpty else { return }
            blocks.append(.text(textLines.joined(separator: "\n")))
            textLines.removeAll()
        }

        for line in lines {
            if line.hasPrefix("```") {
                if inCode {
                    blocks.append(.code(language: language, content: codeLines.joined(separator: "\n")))
                    codeLines.removeAll()
                    language = nil
                } else {
                    flushText()
                    language = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                }
                inCode.toggle()
            } else if inCode {
                codeLines.append(line)
            } else {
                textLines.append(line)
            }
        }

        if inCode {
            textLines.append("```\(language ?? "")")
            textLines.append(contentsOf: codeLines)
        }
        flushText()
        return blocks.isEmpty ? [.text("")] : blocks
    }
}

private enum SyntaxHighlighter {
    static func highlight(_ code: String, language _: String?) -> AttributedString {
        let result = NSMutableAttributedString(string: code)
        let fullRange = NSRange(location: 0, length: result.length)
        let baseColor = UIColor.label
        let keywordColor = UIColor.systemPurple
        let stringColor = UIColor.systemGreen
        let commentColor = UIColor.secondaryLabel

        result.addAttribute(.foregroundColor, value: baseColor, range: fullRange)
        apply(#""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'"#, color: stringColor, to: result)
        apply(#"//.*|#.*"#, color: commentColor, to: result)

        let keywords = "class|struct|enum|func|var|let|if|else|for|while|return|import|async|await|throws|try|guard|case|switch|private|public|final|true|false|nil"
        apply(#"\b(\#(keywords))\b"#, color: keywordColor, to: result)
        return AttributedString(result)
    }

    private static func apply(_ pattern: String, color: UIColor, to value: NSMutableAttributedString) {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return }
        let range = NSRange(location: 0, length: value.length)
        regex.enumerateMatches(in: value.string, range: range) { match, _, _ in
            guard let match else { return }
            value.addAttribute(.foregroundColor, value: color, range: match.range)
        }
    }
}

struct TypingIndicatorView: View {
    @State private var animating = false

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(.secondary)
                    .frame(width: 7, height: 7)
                    .offset(y: animating ? -3 : 3)
                    .animation(
                        .easeInOut(duration: 0.55).repeatForever().delay(Double(index) * 0.12),
                        value: animating
                    )
            }
        }
        .padding(.horizontal, 15)
        .padding(.vertical, 13)
        .background(DoomTheme.assistantBubble, in: Capsule())
        .padding(.leading, 52)
        .onAppear { animating = true }
        .accessibilityLabel("DoomDoja is responding")
    }
}
