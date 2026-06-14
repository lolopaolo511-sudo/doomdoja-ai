import Foundation
import Observation

@Observable
final class AppSettings {
    var baseURLString: String {
        didSet { UserDefaults.standard.set(baseURLString, forKey: "baseURL") }
    }
    var apiKey: String {
        didSet { UserDefaults.standard.set(apiKey, forKey: "apiKey") }
    }
    var modelName: String {
        didSet { UserDefaults.standard.set(modelName, forKey: "modelName") }
    }

    init() {
        self.baseURLString = UserDefaults.standard.string(forKey: "baseURL") ?? "http://localhost:11434"
        self.apiKey = UserDefaults.standard.string(forKey: "apiKey") ?? ""
        self.modelName = UserDefaults.standard.string(forKey: "modelName") ?? "doomdoja"
    }

    var baseURL: URL? {
        // Normalise: strip trailing slash so path appending works correctly
        let raw = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let stripped = raw.hasSuffix("/") ? String(raw.dropLast()) : raw
        return URL(string: stripped)
    }

    var isConfigured: Bool {
        baseURL != nil && !modelName.isEmpty
    }
}
