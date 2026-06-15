import SwiftUI
import SwiftData

@main
struct DoomDojaApp: App {
    let container: ModelContainer
    let settings = AppSettings()

    init() {
        do {
            container = try ModelContainer(for: Chat.self, Message.self)
        } catch {
            fatalError("SwiftData container failed to initialise: \(error)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .modelContainer(container)
                .environment(settings)
        }
    }
}

private struct RootView: View {
    @Environment(\.modelContext) private var modelContext

    @State private var store: ChatStore?
    @AppStorage("didCompleteOnboarding") private var didCompleteOnboarding = false

    var body: some View {
        Group {
            if let store {
                ConversationListView()
                    .environment(store)
                    .fullScreenCover(isPresented: onboardingPresented) {
                        OnboardingView(isPresented: onboardingPresented)
                    }
            } else {
                ProgressView()
                    .onAppear { store = ChatStore(modelContext: modelContext) }
            }
        }
    }

    private var onboardingPresented: Binding<Bool> {
        Binding(
            get: { !didCompleteOnboarding },
            set: { if !$0 { didCompleteOnboarding = true } }
        )
    }
}
