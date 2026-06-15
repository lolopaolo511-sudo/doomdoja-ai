import SwiftUI

// Splits raw text into alternating plain-text and fenced-code segments.
private enum ContentSegment: Identifiable {
    case text(String)
    case codeBlock(language: String, code: String)

    var id: String {
        switch self {
        case .text(let s): return "t\(s.hashValue)"
        case .codeBlock(let l, let c): return "c\(l)\(c.hashValue)"
        }
    }
}

private func parseMarkdown(_ raw: String) -> [ContentSegment] {
    var result: [ContentSegment] = []
    var remaining = raw

    while !remaining.isEmpty {
        guard let fenceStart = remaining.range(of: "```") else {
            result.append(.text(remaining))
            return result
        }

        let before = String(remaining[..<fenceStart.lowerBound])
        if !before.isEmpty { result.append(.text(before)) }
        remaining = String(remaining[fenceStart.upperBound...])

        // Language label on the first line after the opening fence
        let nlIdx = remaining.firstIndex(of: "\n") ?? remaining.endIndex
        let lang = String(remaining[..<nlIdx]).trimmingCharacters(in: .whitespaces)
        remaining = nlIdx < remaining.endIndex
            ? String(remaining[remaining.index(after: nlIdx)...])
            : ""

        if let fenceEnd = remaining.range(of: "```") {
            var code = String(remaining[..<fenceEnd.lowerBound])
            if code.hasSuffix("\n") { code = String(code.dropLast()) }
            result.append(.codeBlock(language: lang, code: code))
            remaining = String(remaining[fenceEnd.upperBound...])
            if remaining.hasPrefix("\n") { remaining = String(remaining.dropFirst()) }
        } else {
            result.append(.codeBlock(language: lang, code: remaining))
            remaining = ""
        }
    }

    return result
}

struct MarkdownContentView: View {
    let text: String

    var body: some View {
        let segments = parseMarkdown(text)
        VStack(alignment: .leading, spacing: 8) {
            ForEach(segments) { segment in
                switch segment {
                case .text(let t):
                    InlineMarkdownView(text: t)
                case .codeBlock(let lang, let code):
                    CodeBlockView(language: lang, code: code)
                }
            }
        }
    }
}

struct InlineMarkdownView: View {
    let text: String

    private var attributed: AttributedString {
        (try? AttributedString(
            markdown: text,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        )) ?? AttributedString(text)
    }

    var body: some View {
        Text(attributed)
            .textSelection(.enabled)
            .fixedSize(horizontal: false, vertical: true)
    }
}
