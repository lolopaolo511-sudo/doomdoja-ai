import SwiftUI

struct SettingsView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(ChatStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @State private var isTesting = false
    @State private var testResult: String?
    @State private var showAPIKey = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    LabeledContent("Status") {
                        if isTesting {
                            ProgressView().controlSize(.small)
                        } else {
                            ConnectionBadge(status: store.connectionStatus)
                        }
                    }
                    Button {
                        Task { await testConnection() }
                    } label: {
                        Label("Test connection", systemImage: "network")
                    }
                    .disabled(isTesting)

                    if let testResult {
                        Text(testResult)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Server") {
                    @Bindable var settings = settings
                    TextField("Base URL", text: $settings.baseURLString)
                        .textContentType(.URL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    HStack {
                        Group {
                            if showAPIKey {
                                TextField("API key (optional)", text: $settings.apiKey)
                            } else {
                                SecureField("API key (optional)", text: $settings.apiKey)
                            }
                        }
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        Button(showAPIKey ? "Hide" : "Show") { showAPIKey.toggle() }
                            .font(.caption)
                    }

                    TextField("Model name", text: $settings.modelName)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("Connect safely") {
                    GuidanceRow(
                        icon: "lock.shield",
                        title: "Tailscale",
                        detail: "Recommended for simple, private access between your iPhone and Mac Mini."
                    )
                    GuidanceRow(
                        icon: "network.badge.shield.half.filled",
                        title: "Cloudflare Tunnel",
                        detail: "Use an authenticated tunnel when you need a public HTTPS endpoint."
                    )
                    Text("Never expose Ollama, LM Studio, or another model server directly to the public internet.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func testConnection() async {
        isTesting = true
        testResult = nil
        await store.testConnection(settings: settings)
        isTesting = false
        switch store.connectionStatus {
        case .connected: testResult = "Successfully reached the server."
        case .disconnected: testResult = "Could not connect. Check the URL and server."
        case .unknown: testResult = nil
        }
    }
}

private struct GuidanceRow: View {
    let icon: String
    let title: String
    let detail: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(DoomTheme.accent)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(detail).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
