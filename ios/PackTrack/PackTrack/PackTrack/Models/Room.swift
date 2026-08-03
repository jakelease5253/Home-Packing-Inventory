import Foundation

struct Room: Identifiable, Codable {
    let id: Int
    let name: String
    let isCustom: Bool
    let boxCount: Int
    let itemCount: Int
    let sealedCount: Int
    let boxNumbers: [Int]
    let boxNumbersDisplay: String

    enum CodingKeys: String, CodingKey {
        case id, name
        case isCustom = "is_custom"
        case boxCount = "box_count"
        case itemCount = "item_count"
        case sealedCount = "sealed_count"
        case boxNumbers = "box_numbers"
        case boxNumbersDisplay = "box_numbers_display"
    }
}
