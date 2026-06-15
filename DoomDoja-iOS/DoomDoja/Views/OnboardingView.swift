import SwiftUI

struct OnboardingView: View {
    @Binding var isPresented: Bool

    var body: some View {
        TabView {
            OnboardingPage(
                icon: "sparkles",
                title: "Meet DoomDoja",
                detail: "A polished, private chat experience powered by the model running on your Mac Mini."
            )
            OnboardingPage(
                icon: "lock.shield",
                title: "Connect securely",
                detail: "Use Tailscale for private access, or an authenticated Cloudflare Tunnel. Never expose your model server directly."
            )
            VStack(spacing: 26) {
                OnboardingPage(
                    icon: "slider.horizontal.3",
                    title: "Configure your server",
                    detail: "Enter the OpenAI-compatible base URL, optional API key, and model name in Settings."
                )
                Button("Get started") { isPresented = false }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(DoomTheme.accent)
            }
            .padding()
        }
        .tabViewStyle(.page(indexDisplayMode: .always))
        .background(Color(uiColor: .systemBackground))
    }
}

private struct OnboardingPage: View {
    let icon: String
    let title: String
    let detail: String

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: icon)
                .font(.system(size: 54, weight: .semibold))
                .foregroundStyle(DoomTheme.accent)
                .accessibilityHidden(true)
            Text(title)
                .font(.largeTitle.bold())
                .multilineTextAlignment(.center)
            Text(detail)
                .font(.title3)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 420)
        }
        .padding(32)
    }
}
