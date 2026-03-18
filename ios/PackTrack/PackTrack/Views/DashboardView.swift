import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var api: APIService
    @State private var rooms: [Room] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showCreateBox = false
    @Binding var deepLinkBoxId: String?

    var totalBoxes: Int { rooms.reduce(0) { $0 + $1.boxCount } }
    var totalItems: Int { rooms.reduce(0) { $0 + $1.itemCount } }
    var totalSealed: Int { rooms.reduce(0) { $0 + $1.sealedCount } }
    var roomsWithBoxes: [Room] { rooms.filter { $0.boxCount > 0 } }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Stats row
                HStack(spacing: 12) {
                    StatCard(value: "\(rooms.count)", label: "Rooms", color: .blue)
                    StatCard(value: "\(totalBoxes)", label: "Boxes", color: .orange)
                    StatCard(value: "\(totalItems)", label: "Items", color: .green)
                    StatCard(value: "\(totalSealed)", label: "Sealed", color: .purple)
                }
                .padding(.horizontal)

                // Room list
                if roomsWithBoxes.isEmpty && !isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "house")
                            .font(.system(size: 48))
                            .foregroundStyle(.secondary)
                        Text("No rooms with boxes yet")
                            .font(.headline)
                        Text("Tap + to create your first box")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 60)
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(roomsWithBoxes) { room in
                            NavigationLink(value: room.id) {
                                RoomCardView(room: room)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
        .navigationTitle("PackTrack")
        .navigationDestination(for: Int.self) { roomId in
            RoomDetailView(roomId: roomId, onUpdate: { loadRooms() })
        }
        .navigationDestination(for: String.self) { boxId in
            BoxDetailView(boxId: boxId, onDelete: { loadRooms() })
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { showCreateBox = true } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showCreateBox) {
            CreateBoxView { _ in loadRooms() }
        }
        .refreshable { await refreshRooms() }
        .task { await refreshRooms() }
        .overlay {
            if isLoading && rooms.isEmpty {
                ProgressView("Loading...")
            }
        }
    }

    func loadRooms() {
        Task { await refreshRooms() }
    }

    func refreshRooms() async {
        isLoading = true
        defer { isLoading = false }
        do {
            rooms = try await api.getRooms()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let value: String
    let label: String
    var color: Color = .blue

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2.bold())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Room Card

struct RoomCardView: View {
    let room: Room

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(room.name)
                        .font(.headline)
                    Text("\(room.boxCount) box\(room.boxCount == 1 ? "" : "es") \u{2022} \(room.itemCount) item\(room.itemCount == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if room.sealedCount == room.boxCount && room.boxCount > 0 {
                    Text("All Sealed")
                        .font(.caption2.bold())
                        .textCase(.uppercase)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.green.opacity(0.2))
                        .foregroundStyle(.green)
                        .clipShape(Capsule())
                } else if room.sealedCount > 0 {
                    Text("\(room.sealedCount)/\(room.boxCount) Sealed")
                        .font(.caption2.bold())
                        .textCase(.uppercase)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.orange.opacity(0.2))
                        .foregroundStyle(.orange)
                        .clipShape(Capsule())
                }
            }

            if !room.boxNumbersDisplay.isEmpty {
                HStack {
                    Label("Boxes: \(room.boxNumbersDisplay)", systemImage: "shippingbox")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(Color(.separator).opacity(0.3), lineWidth: 1)
        )
    }
}
