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
    @Environment(AppSettings.self) private var settings
    @AppStorage("hasSeenOnboarding") private var hasSeenOnboarding = false

    @State private var store: ChatStore?

    var body: some View {
        Group {
            if let store {
                ConversationListView()
                    .environment(store)
                    .fullScreenCover(isPresented: Binding(
                        get: { !hasSeenOnboarding },
                        set: { if !$0 { hasSeenOnboarding = true } }
                    )) {
                        OnboardingView()
                    }
            } else {
                ProgressView()
                    .onAppear { store = ChatStore(modelContext: modelContext) }
            }
        }
    }
}
