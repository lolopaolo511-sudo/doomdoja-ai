import SwiftUI

struct SettingsView: View {
    @Environment(AppSettings.self) private var settings
    @Environment(ChatStore.self) private var store
    @Environment(\.dismiss) private var dismiss

    @State private var isTesting = false
    @State private var testResult: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    @Bindable var s = settings
                    LabeledContent("Server URL") {
                        TextField("http://192.168.1.x:11434", text: $s.baseURLString)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                            .multilineTextAlignment(.trailing)
                    }
                    LabeledContent("API Key") {
                        SecureField("Optional", text: $s.apiKey)
                            .multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Model name") {
                        TextField("doomdoja", text: $s.modelName)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .multilineTextAlignment(.trailing)
                    }
                } header: {
                    Text("Connection")
                }

                Section {
                    HStack {
                        Button {
                            Task { await testConn() }
                        } label: {
                            Label("Test Connection", systemImage: "network")
                        }
                        .disabled(isTesting)

                        Spacer()

                        if isTesting {
                            ProgressView()
                        } else {
                            statusBadge
                        }
                    }

                    if let result = testResult {
                        Text(result)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    onboardingContent
                } header: {
                    Text("How to connect your Mac Mini")
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

    @ViewBuilder
    private var statusBadge: some View {
        switch store.connectionStatus {
        case .connected:
            Label("Connected", systemImage: "checkmark.circle.fill")
                .font(.caption)
                .foregroundStyle(.green)
        case .disconnected:
            Label("Offline", systemImage: "xmark.circle.fill")
                .font(.caption)
                .foregroundStyle(.red)
        case .unknown:
            Label("Unknown", systemImage: "questionmark.circle")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var onboardingContent: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Your DoomDoja model runs on a Mac Mini and exposes an OpenAI-compatible API (e.g. Ollama or LM Studio). The iOS app connects to that server over your network.")
                .font(.caption)
                .foregroundStyle(.secondary)

            Text("Safe ways to expose your Mac Mini:")
                .font(.caption.weight(.semibold))

            ForEach([
                ("Tailscale", "Zero-config private VPN. Install on both Mac and iPhone for a secure tunnel."),
                ("Cloudflare Tunnel", "Use `cloudflared` on the Mac to create a public HTTPS endpoint."),
                ("Local Wi-Fi", "Connect both devices to the same Wi-Fi. Use your Mac's local IP address."),
            ], id: \.0) { name, desc in
                VStack(alignment: .leading, spacing: 2) {
                    Text("• \(name)")
                        .font(.caption.weight(.medium))
                    Text(desc)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func testConn() async {
        isTesting = true
        testResult = nil
        await store.testConnection(settings: settings)
        isTesting = false
        switch store.connectionStatus {
        case .connected: testResult = "Successfully reached the server."
        case .disconnected: testResult = "Could not connect. Check the URL and that the server is running."
        case .unknown: testResult = nil
        }
    }
}
