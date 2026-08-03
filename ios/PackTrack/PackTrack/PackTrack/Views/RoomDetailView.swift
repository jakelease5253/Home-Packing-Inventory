import SwiftUI

struct RoomDetailView: View {
    let roomId: Int
    var onUpdate: (() -> Void)?

    @EnvironmentObject var api: APIService
    @State private var boxes: [Box] = []
    @State private var roomName: String = ""
    @State private var isLoading = true
    @State private var showCreateBox = false
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Stats
                HStack(spacing: 12) {
                    StatCard(value: "\(boxes.count)", label: "Boxes", color: .orange)
                    StatCard(value: "\(boxes.reduce(0) { $0 + $1.itemCount })", label: "Items", color: .green)
                    StatCard(value: "\(boxes.filter(\.sealed).count)", label: "Sealed", color: .purple)
                    StatCard(value: "\(boxes.filter { !$0.sealed }.count)", label: "Open", color: .blue)
                }
                .padding(.horizontal)

                // Box list
                if boxes.isEmpty && !isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "shippingbox")
                            .font(.system(size: 48))
                            .foregroundStyle(.secondary)
                        Text("No boxes in this room yet")
                            .font(.headline)
                        Button("Add Box") { createBox() }
                            .buttonStyle(.borderedProminent)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 40)
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(boxes) { box in
                            NavigationLink(value: box.id) {
                                BoxCardView(box: box)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
        .navigationTitle(roomName)
        .navigationBarTitleDisplayMode(.large)
        .navigationDestination(for: String.self) { boxId in
            BoxDetailView(boxId: boxId, onDelete: { loadBoxes() })
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { createBox() } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .refreshable { await refreshBoxes() }
        .task { await refreshBoxes() }
        .overlay {
            if isLoading && boxes.isEmpty {
                ProgressView("Loading...")
            }
        }
    }

    func createBox() {
        Task {
            do {
                _ = try await api.createBox(BoxCreate(roomId: roomId))
                await refreshBoxes()
                onUpdate?()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    func loadBoxes() {
        Task {
            await refreshBoxes()
            onUpdate?()
        }
    }

    func refreshBoxes() async {
        isLoading = true
        defer { isLoading = false }
        do {
            boxes = try await api.getBoxes(roomId: roomId)
            if let first = boxes.first {
                roomName = first.roomName
            } else {
                // Get room name from rooms list
                let rooms = try await api.getRooms()
                roomName = rooms.first(where: { $0.id == roomId })?.name ?? "Room"
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Box Card

struct BoxCardView: View {
    let box: Box

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(box.name)
                        .font(.headline)
                    if !box.notes.isEmpty {
                        Text(box.notes)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
                Text(box.sealed ? "Sealed" : "Open")
                    .font(.caption2.bold())
                    .textCase(.uppercase)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(box.sealed ? Color.green.opacity(0.2) : Color.yellow.opacity(0.2))
                    .foregroundStyle(box.sealed ? .green : .orange)
                    .clipShape(Capsule())
            }

            if !box.items.isEmpty {
                Text(box.items.prefix(3).map(\.name).joined(separator: ", ")
                     + (box.items.count > 3 ? " +\(box.items.count - 3) more" : ""))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            HStack {
                Label("\(box.itemCount) item\(box.itemCount == 1 ? "" : "s")", systemImage: "tray")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding()
        .background(box.sealed ? Color.green.opacity(0.04) : Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(box.sealed ? Color.green.opacity(0.3) : Color(.separator).opacity(0.3), lineWidth: 1)
        )
    }
}
