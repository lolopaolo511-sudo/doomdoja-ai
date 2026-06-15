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
                connectionSection
                testSection
                connectGuideSection
                aboutSection
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .fontWeight(.semibold)
                }
            }
        }
    }

    // MARK: - Connection fields

    private var connectionSection: some View {
        Section {
            @Bindable var s = settings

            HStack {
                Label("Server URL", systemImage: "server.rack")
                Spacer()
                TextField("http://192.168.x.x:11434", text: $s.baseURLString)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .multilineTextAlignment(.trailing)
                    .foregroundStyle(.secondary)
            }

            HStack {
                Label("API Key", systemImage: "key")
                Spacer()
                SecureField("Optional", text: $s.apiKey)
                    .multilineTextAlignment(.trailing)
                    .foregroundStyle(.secondary)
            }

            HStack {
                Label("Model", systemImage: "cpu")
                Spacer()
                TextField("doomdoja", text: $s.modelName)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .multilineTextAlignment(.trailing)
                    .foregroundStyle(.secondary)
            }
        } header: {
            HStack {
                Text("Connection")
                Spacer()
                statusPill
            }
            .textCase(nil)
        }
    }

    // MARK: - Connection test

    private var testSection: some View {
        Section {
            Button {
                Task { await testConn() }
            } label: {
                HStack {
                    Label("Test Connection", systemImage: "network")
                    Spacer()
                    if isTesting { ProgressView() }
                }
            }
            .disabled(isTesting)

            if let result = testResult {
                Text(result)
                    .font(.footnote)
                    .foregroundStyle(store.connectionStatus == .connected ? .green : .secondary)
            }
        }
    }

    // MARK: - Connection guide

    private var connectGuideSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                Text("DoomDoja runs on your Mac Mini and exposes an OpenAI-compatible API. Configure your iPhone to reach it using one of these options:")
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                ForEach([
                    ("network.badge.shield.half.filled", "Tailscale", "Install on both devices. Zero-config encrypted private tunnel — the easiest option."),
                    ("cloud", "Cloudflare Tunnel", "Run `cloudflared` on your Mac for a secure public HTTPS endpoint."),
                    ("wifi", "Local Wi-Fi", "Use your Mac's local IP when both devices are on the same network."),
                ], id: \.1) { icon, name, desc in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: icon)
                            .font(.footnote)
                            .foregroundStyle(Color.accentColor)
                            .frame(width: 18)
                            .padding(.top, 1)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(name).font(.footnote.weight(.semibold))
                            Text(desc).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .padding(.vertical, 4)
        } header: {
            Text("How to connect your Mac Mini")
        }
    }

    // MARK: - About

    private var aboutSection: some View {
        Section {
            HStack {
                Text("Version")
                Spacer()
                Text("1.0")
                    .foregroundStyle(.secondary)
            }
        } footer: {
            Text("DoomDoja — your local AI, always private.")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.top, 8)
        }
    }

    // MARK: - Status pill

    private var statusPill: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(statusColor)
                .frame(width: 7, height: 7)
            Text(statusLabel)
                .font(.caption)
                .foregroundStyle(statusColor)
        }
    }

    private var statusColor: Color {
        switch store.connectionStatus {
        case .connected: .green
        case .disconnected: .red
        case .unknown: Color(.tertiaryLabel)
        }
    }

    private var statusLabel: String {
        switch store.connectionStatus {
        case .connected: "Online"
        case .disconnected: "Offline"
        case .unknown: "Unknown"
        }
    }

    // MARK: - Actions

    private func testConn() async {
        isTesting = true
        testResult = nil
        await store.testConnection(settings: settings)
        isTesting = false
        testResult = store.connectionStatus == .connected
            ? "Successfully connected to the server."
            : "Could not connect. Check the URL and that your server is running."
    }
}
