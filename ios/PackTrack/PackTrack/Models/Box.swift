import Foundation

struct Box: Identifiable, Codable {
    let id: String
    var name: String
    var location: String
    var notes: String
    var sealed: Bool
    let createdAt: String
    var itemCount: Int
    var items: [Item]

    enum CodingKeys: String, CodingKey {
        case id, name, location, notes, sealed, items
        case createdAt = "created_at"
        case itemCount = "item_count"
    }
}

struct BoxCreate: Codable {
    let name: String
    var location: String = ""
    var notes: String = ""
}
