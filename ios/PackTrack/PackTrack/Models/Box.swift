import Foundation

struct Box: Identifiable, Codable {
    let id: String
    var number: Int
    var name: String
    var roomId: Int
    var roomName: String
    var location: String
    var notes: String
    var sealed: Bool
    let createdAt: String
    var itemCount: Int
    var items: [Item]

    enum CodingKeys: String, CodingKey {
        case id, number, name, location, notes, sealed, items
        case roomId = "room_id"
        case roomName = "room_name"
        case createdAt = "created_at"
        case itemCount = "item_count"
    }
}

struct BoxCreate: Codable {
    let roomId: Int
    var notes: String = ""

    enum CodingKeys: String, CodingKey {
        case roomId = "room_id"
        case notes
    }
}
