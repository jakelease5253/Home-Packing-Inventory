import Foundation
import UIKit

/// Centralized networking layer that talks to the PackTrack Flask backend.
@MainActor
class APIService: ObservableObject {
    static let shared = APIService()

    /// Base URL of the Flask server. Change this to your server's address.
    @Published var baseURL: String {
        didSet { UserDefaults.standard.set(baseURL, forKey: "serverURL") }
    }

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init() {
        self.baseURL = UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:5000"
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        self.session = URLSession(configuration: config)
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    // MARK: - Boxes

    func getBoxes() async throws -> [Box] {
        return try await get("/api/boxes")
    }

    func getBox(id: String) async throws -> Box {
        return try await get("/api/boxes/\(id)")
    }

    func createBox(_ box: BoxCreate) async throws -> Box {
        return try await post("/api/boxes", body: box)
    }

    func updateBox(id: String, data: [String: Any]) async throws -> Box {
        return try await request("/api/boxes/\(id)", method: "PUT", jsonDict: data)
    }

    func deleteBox(id: String) async throws {
        let _: [String: Bool] = try await request("/api/boxes/\(id)", method: "DELETE")
    }

    func sealBox(id: String) async throws -> Box {
        return try await post("/api/boxes/\(id)/seal", body: Optional<String>.none)
    }

    func unsealBox(id: String) async throws -> Box {
        return try await post("/api/boxes/\(id)/unseal", body: Optional<String>.none)
    }

    // MARK: - Items

    func addItem(boxId: String, item: ItemCreate) async throws -> Item {
        return try await post("/api/boxes/\(boxId)/items", body: item)
    }

    func addItemsBulk(boxId: String, items: [ItemCreate]) async throws -> [Item] {
        return try await post("/api/boxes/\(boxId)/items/bulk", body: BulkItemCreate(items: items))
    }

    func updateItem(id: Int, data: [String: Any]) async throws -> Item {
        return try await request("/api/items/\(id)", method: "PUT", jsonDict: data)
    }

    func deleteItem(id: Int) async throws {
        let _: [String: Bool] = try await request("/api/items/\(id)", method: "DELETE")
    }

    // MARK: - Photos

    func uploadPhoto(_ image: UIImage) async throws -> PhotoAnalysisResult {
        guard let url = URL(string: "\(baseURL)/api/analyze-photo") else {
            throw APIError.invalidURL
        }

        let boundary = UUID().uuidString
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        guard let imageData = image.jpegData(compressionQuality: 0.8) else {
            throw APIError.encodingFailed
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"photo\"; filename=\"photo.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.serverError
        }
        return try decoder.decode(PhotoAnalysisResult.self, from: data)
    }

    // MARK: - QR Code URL

    func qrCodeURL(boxId: String) -> URL? {
        URL(string: "\(baseURL)/api/boxes/\(boxId)/qr")
    }

    func boxDeepLink(boxId: String) -> String {
        "\(baseURL)/?box=\(boxId)"
    }

    // MARK: - Search

    func searchBoxes(query: String) async throws -> [Box] {
        let encoded = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await get("/api/boxes/search?q=\(encoded)")
    }

    // MARK: - Private helpers

    private func get<T: Decodable>(_ path: String) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.serverError
        }
        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Decodable, B: Encodable>(_ path: String, body: B?) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let body = body {
            req.httpBody = try encoder.encode(body)
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            if let http = response as? HTTPURLResponse, let errData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let msg = errData["error"] as? String {
                throw APIError.message(msg)
            }
            throw APIError.serverError
        }
        return try decoder.decode(T.self, from: data)
    }

    private func request<T: Decodable>(_ path: String, method: String, jsonDict: [String: Any]? = nil) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let dict = jsonDict {
            req.httpBody = try JSONSerialization.data(withJSONObject: dict)
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            if let errData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let msg = errData["error"] as? String {
                throw APIError.message(msg)
            }
            throw APIError.serverError
        }
        return try decoder.decode(T.self, from: data)
    }
}

struct PhotoAnalysisResult: Codable {
    let message: String
    let photoPreview: String?
    let detectedItems: [DetectedItem]

    enum CodingKeys: String, CodingKey {
        case message
        case photoPreview = "photo_preview"
        case detectedItems = "detected_items"
    }
}

struct DetectedItem: Codable {
    let name: String
}

enum APIError: LocalizedError {
    case invalidURL
    case serverError
    case encodingFailed
    case message(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid server URL"
        case .serverError: return "Server error"
        case .encodingFailed: return "Failed to encode data"
        case .message(let msg): return msg
        }
    }
}
