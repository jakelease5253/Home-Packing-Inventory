import Foundation

struct Item: Identifiable, Codable {
    let id: Int
    var name: String
    var quantity: Int
    var category: String
    let boxId: String

    enum CodingKeys: String, CodingKey {
        case id, name, quantity, category
        case boxId = "box_id"
    }
}

struct ItemCreate: Codable {
    let name: String
    var quantity: Int = 1
    var category: String = ""
}

struct BulkItemCreate: Codable {
    let items: [ItemCreate]
}
