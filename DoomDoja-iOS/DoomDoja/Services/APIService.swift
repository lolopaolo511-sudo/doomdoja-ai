import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse(statusCode: Int)
    case decodingError(String)
    case networkError(Error)
    case streamEnded

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid server URL. Please check Settings."
        case .invalidResponse(let code): return "Server returned error \(code)."
        case .decodingError(let msg): return "Failed to decode response: \(msg)"
        case .networkError(let err): return err.localizedDescription
        case .streamEnded: return "Stream ended unexpectedly."
        }
    }
}

struct APIService {

    // MARK: - Streaming chat completions

    func sendMessageStream(
        messages: [Message],
        model: String,
        baseURL: URL,
        apiKey: String?
    ) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let request = try buildRequest(
                        messages: messages,
                        model: model,
                        baseURL: baseURL,
                        apiKey: apiKey
                    )

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)

                    guard let http = response as? HTTPURLResponse else {
                        continuation.finish(throwing: APIError.invalidResponse(statusCode: -1))
                        return
                    }
                    guard (200..<300).contains(http.statusCode) else {
                        continuation.finish(throwing: APIError.invalidResponse(statusCode: http.statusCode))
                        return
                    }

                    for try await line in bytes.lines {
                        guard line.hasPrefix("data: ") else { continue }
                        let data = String(line.dropFirst(6))
                        if data == "[DONE]" { break }

                        guard let jsonData = data.data(using: .utf8),
                              let chunk = try? JSONDecoder().decode(StreamChunk.self, from: jsonData),
                              let delta = chunk.choices.first?.delta.content
                        else { continue }

                        continuation.yield(delta)
                    }

                    continuation.finish()
                } catch {
                    continuation.finish(throwing: APIError.networkError(error))
                }
            }
        }
    }

    // MARK: - Connection test

    func testConnection(baseURL: URL, apiKey: String?) async -> Result<Void, Error> {
        do {
            var url = baseURL
            url.appendPathComponent("v1/models")
            var request = URLRequest(url: url, timeoutInterval: 8)
            if let key = apiKey, !key.isEmpty {
                request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            }
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                return .failure(APIError.invalidResponse(statusCode: (response as? HTTPURLResponse)?.statusCode ?? -1))
            }
            return .success(())
        } catch {
            return .failure(APIError.networkError(error))
        }
    }

    // MARK: - Private helpers

    private func buildRequest(
        messages: [Message],
        model: String,
        baseURL: URL,
        apiKey: String?
    ) throws -> URLRequest {
        var url = baseURL
        url.appendPathComponent("v1/chat/completions")

        guard url.scheme != nil else { throw APIError.invalidURL }

        var request = URLRequest(url: url, timeoutInterval: 60)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let key = apiKey, !key.isEmpty {
            request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "model": model,
            "messages": messages.map { $0.apiRepresentation },
            "stream": true
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }
}

// MARK: - SSE decoding models

private struct StreamChunk: Decodable {
    let choices: [Choice]

    struct Choice: Decodable {
        let delta: Delta
    }

    struct Delta: Decodable {
        let content: String?
    }
}
