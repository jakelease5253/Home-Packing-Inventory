import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var api: APIService
    @State private var serverURL: String = ""
    @State private var apiKey: String = ""
    @State private var connectionStatus: ConnectionStatus = .unknown
    @State private var isTesting = false

    enum ConnectionStatus {
        case unknown, connected, failed
    }

    var body: some View {
        Form {
            Section {
                TextField("Server URL", text: $serverURL)
                    .textContentType(.URL)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .onSubmit { saveURL() }

                SecureField("API Key (if required)", text: $apiKey)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .onSubmit { saveURL() }

                HStack {
                    Button("Save & Test") { saveURL() }
                        .disabled(isTesting)

                    Spacer()

                    switch connectionStatus {
                    case .unknown:
                        EmptyView()
                    case .connected:
                        Label("Connected", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                            .font(.subheadline)
                    case .failed:
                        Label("Failed", systemImage: "xmark.circle.fill")
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                }
            } header: {
                Text("Server Connection")
            } footer: {
                Text("Enter the URL where your PackTrack server is running (e.g., https://packtrack.up.railway.app), plus the API key if the server requires one.")
            }

            Section("About") {
                HStack {
                    Text("App")
                    Spacer()
                    Text("PackTrack")
                        .foregroundStyle(.secondary)
                }
                HStack {
                    Text("Version")
                    Spacer()
                    Text("1.0.0")
                        .foregroundStyle(.secondary)
                }
            }

            Section("Tips") {
                Label("Create boxes for each room or category", systemImage: "lightbulb")
                Label("Use Bulk Photo to add items quickly", systemImage: "camera")
                Label("Seal boxes when done packing them", systemImage: "lock")
                Label("Print QR labels and tape them to boxes", systemImage: "qrcode")
                Label("Scan QR codes to find items fast on moving day", systemImage: "qrcode.viewfinder")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
        .navigationTitle("Settings")
        .onAppear {
            serverURL = api.baseURL
            apiKey = api.apiKey
        }
    }

    func saveURL() {
        let trimmed = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        api.baseURL = trimmed
        serverURL = trimmed
        api.apiKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        testConnection()
    }

    func testConnection() {
        isTesting = true
        connectionStatus = .unknown
        Task {
            do {
                _ = try await api.getBoxes()
                connectionStatus = .connected
            } catch {
                connectionStatus = .failed
            }
            isTesting = false
        }
    }
}
