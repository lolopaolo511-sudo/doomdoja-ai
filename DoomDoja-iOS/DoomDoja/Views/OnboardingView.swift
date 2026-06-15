import SwiftUI

struct OnboardingView: View {
    @AppStorage("hasSeenOnboarding") private var hasSeenOnboarding = false
    @State private var currentPage = 0

    private let pages: [OPage] = [
        OPage(
            symbol: "brain.head.profile",
            color: .purple,
            title: "Meet DoomDoja",
            body: "Your personal AI model running on your own Mac Mini — **no subscriptions, no data leaving your home**."
        ),
        OPage(
            symbol: "network",
            color: .blue,
            title: "Connect Securely",
            body: "DoomDoja talks to your Mac Mini over the network. Three easy options:\n\n**Tailscale** — install on both devices for a zero-config encrypted tunnel.\n\n**Cloudflare Tunnel** — run `cloudflared` on your Mac to get a public HTTPS endpoint.\n\n**Local Wi-Fi** — use your Mac's local IP when both devices are on the same network."
        ),
        OPage(
            symbol: "checkmark.seal.fill",
            color: .green,
            title: "You're Ready",
            body: "Open **Settings** ⚙ to enter your Mac Mini's address and model name.\n\nThen start your first conversation — DoomDoja is waiting."
        ),
    ]

    var body: some View {
        VStack(spacing: 0) {
            TabView(selection: $currentPage) {
                ForEach(Array(pages.enumerated()), id: \.offset) { index, page in
                    pageView(page).tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))

            bottomControls
        }
        .background(Color(.systemBackground))
        .interactiveDismissDisabled()
    }

    // MARK: Page

    private func pageView(_ page: OPage) -> some View {
        VStack(spacing: 0) {
            Spacer()

            ZStack {
                Circle()
                    .fill(page.color.opacity(0.12))
                    .frame(width: 130, height: 130)
                Image(systemName: page.symbol)
                    .font(.system(size: 56, weight: .semibold))
                    .foregroundStyle(page.color)
            }
            .padding(.bottom, 36)

            Text(page.title)
                .font(.largeTitle.weight(.bold))
                .multilineTextAlignment(.center)
                .padding(.bottom, 16)

            if let attr = try? AttributedString(markdown: page.body) {
                Text(attr)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineSpacing(3)
                    .padding(.horizontal, 36)
            }

            Spacer()
        }
    }

    // MARK: Bottom controls

    private var bottomControls: some View {
        VStack(spacing: 24) {
            HStack(spacing: 8) {
                ForEach(0..<pages.count, id: \.self) { i in
                    Capsule()
                        .fill(i == currentPage ? Color.accentColor : Color(.tertiaryLabel))
                        .frame(width: i == currentPage ? 22 : 8, height: 8)
                        .animation(.spring(response: 0.3, dampingFraction: 0.7), value: currentPage)
                }
            }

            if currentPage < pages.count - 1 {
                HStack {
                    Button("Skip") { hasSeenOnboarding = true }
                        .foregroundStyle(.secondary)
                        .font(.subheadline)
                    Spacer()
                    nextButton
                }
                .padding(.horizontal, 28)
            } else {
                getStartedButton
                    .padding(.horizontal, 28)
            }
        }
        .padding(.bottom, 52)
    }

    private var nextButton: some View {
        Button {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) { currentPage += 1 }
        } label: {
            HStack(spacing: 6) {
                Text("Next")
                Image(systemName: "arrow.right")
            }
            .font(.headline)
            .padding(.horizontal, 28)
            .padding(.vertical, 14)
            .background(Color.accentColor)
            .foregroundStyle(.white)
            .clipShape(Capsule())
        }
    }

    private var getStartedButton: some View {
        Button {
            withAnimation { hasSeenOnboarding = true }
        } label: {
            Text("Get Started")
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 17)
                .background(Color.accentColor)
                .foregroundStyle(.white)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
    }
}

private struct OPage {
    let symbol: String
    let color: Color
    let title: String
    let body: String
}
