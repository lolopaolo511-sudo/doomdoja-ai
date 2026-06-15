import SwiftUI

struct CodeBlockView: View {
    let language: String
    let code: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            headerBar
            Divider()
            ScrollView(.horizontal, showsIndicators: false) {
                Text(code)
                    .font(.system(.footnote, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Color(.systemBackground).opacity(0.5))
        }
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(Color(.separator), lineWidth: 0.5)
        )
    }

    private var headerBar: some View {
        HStack(spacing: 0) {
            if !language.isEmpty {
                Text(language.lowercased())
                    .font(.caption.monospaced().weight(.medium))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                UIPasteboard.general.string = code
                withAnimation(.spring(response: 0.25, dampingFraction: 0.7)) { copied = true }
                Task {
                    try? await Task.sleep(for: .seconds(2))
                    withAnimation { copied = false }
                }
            } label: {
                Label(copied ? "Copied!" : "Copy", systemImage: copied ? "checkmark" : "doc.on.doc")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(copied ? .green : .secondary)
                    .contentTransition(.symbolEffect(.replace))
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
}
