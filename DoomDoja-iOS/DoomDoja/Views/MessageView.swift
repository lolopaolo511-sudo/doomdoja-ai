import SwiftUI

struct MessageView: View {
    let message: Message

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.isUser { Spacer(minLength: 48) }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                Text(message.content.isEmpty ? "…" : message.content)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(bubbleBackground)
                    .foregroundStyle(message.isUser ? .white : .primary)
                    .clipShape(BubbleShape(isUser: message.isUser))

                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .padding(.horizontal, 4)
            }

            if !message.isUser { Spacer(minLength: 48) }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 2)
    }

    private var bubbleBackground: some ShapeStyle {
        message.isUser
            ? AnyShapeStyle(Color.accentColor)
            : AnyShapeStyle(Color(.secondarySystemBackground))
    }
}

private struct BubbleShape: Shape {
    let isUser: Bool
    let radius: CGFloat = 18
    let tail: CGFloat = 6

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let tl = CGPoint(x: rect.minX, y: rect.minY + radius)
        let tr = CGPoint(x: rect.maxX, y: rect.minY + radius)
        let bl = CGPoint(x: rect.minX, y: rect.maxY - radius)
        let br = CGPoint(x: rect.maxX, y: rect.maxY - radius)

        path.move(to: CGPoint(x: rect.minX + radius, y: rect.minY))
        path.addArc(center: CGPoint(x: rect.maxX - radius, y: rect.minY + radius),
                    radius: radius, startAngle: .degrees(-90), endAngle: .degrees(0), clockwise: false)
        if isUser {
            path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - tail))
            path.addLine(to: CGPoint(x: rect.maxX + tail, y: rect.maxY))
            path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        } else {
            path.addArc(center: CGPoint(x: rect.maxX - radius, y: rect.maxY - radius),
                        radius: radius, startAngle: .degrees(0), endAngle: .degrees(90), clockwise: false)
        }
        path.addArc(center: CGPoint(x: rect.minX + radius, y: rect.maxY - radius),
                    radius: isUser ? radius : radius,
                    startAngle: .degrees(90), endAngle: .degrees(180), clockwise: false)
        if !isUser {
            path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY - tail))
            path.addLine(to: CGPoint(x: rect.minX - tail, y: rect.maxY))
            path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        } else {
            path.addArc(center: CGPoint(x: rect.minX + radius, y: rect.minY + radius),
                        radius: radius, startAngle: .degrees(180), endAngle: .degrees(270), clockwise: false)
        }
        path.closeSubpath()
        return path
    }
}

// Typing indicator for Codex to use while streaming begins
struct TypingIndicatorView: View {
    @State private var phase = 0

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3) { i in
                Circle()
                    .frame(width: 8, height: 8)
                    .foregroundStyle(.secondary)
                    .scaleEffect(phase == i ? 1.4 : 1.0)
                    .animation(.easeInOut(duration: 0.4).repeatForever().delay(Double(i) * 0.15), value: phase)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .padding(.leading, 12)
        .padding(.vertical, 2)
        .onAppear { phase = 0 }
    }
}
