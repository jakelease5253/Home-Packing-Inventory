import SwiftUI

struct CreateBoxView: View {
    var onCreate: ((Box) -> Void)?

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var rooms: [Room] = []
    @State private var selectedRoomId: Int?
    @State private var notes = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var showAddRoom = false
    @State private var customRoomName = ""
    @State private var nextBoxNumber: Int?

    var selectedRoom: Room? {
        rooms.first(where: { $0.id == selectedRoomId })
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Room", selection: $selectedRoomId) {
                        Text("Select a room").tag(nil as Int?)
                        ForEach(rooms) { room in
                            Text(room.name).tag(room.id as Int?)
                        }
                    }

                    Button("Add Custom Room...") {
                        showAddRoom = true
                    }
                    .font(.subheadline)
                } header: {
                    Text("Room")
                } footer: {
                    if let room = selectedRoom {
                        let num = (room.boxNumbers.last ?? 0) + 1
                        Text("This will create Box \(num) in \(room.name)")
                    }
                }

                Section {
                    TextField("Notes (optional)", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                } header: {
                    Text("Details")
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                }
            }
            .navigationTitle("New Box")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") { createBox() }
                        .disabled(selectedRoomId == nil || isSaving)
                }
            }
            .task { await loadRooms() }
            .alert("Add Custom Room", isPresented: $showAddRoom) {
                TextField("Room name", text: $customRoomName)
                Button("Add") { addCustomRoom() }
                Button("Cancel", role: .cancel) { customRoomName = "" }
            } message: {
                Text("Enter a name for the custom room.")
            }
        }
    }

    func loadRooms() async {
        do {
            rooms = try await api.getRooms()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func createBox() {
        guard let roomId = selectedRoomId else { return }
        isSaving = true
        Task {
            do {
                let box = try await api.createBox(BoxCreate(
                    roomId: roomId,
                    notes: notes.trimmingCharacters(in: .whitespaces)
                ))
                onCreate?(box)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSaving = false
            }
        }
    }

    func addCustomRoom() {
        let name = customRoomName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        Task {
            do {
                let room = try await api.createRoom(name: name)
                rooms.append(room)
                selectedRoomId = room.id
                customRoomName = ""
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
