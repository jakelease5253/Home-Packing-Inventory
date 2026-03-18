import SwiftUI

struct BoxDetailView: View {
    let boxId: String
    var onDelete: (() -> Void)?

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var box: Box?
    @State private var isLoading = true
    @State private var showAddItem = false
    @State private var showBulkPhoto = false
    @State private var showQRCode = false
    @State private var showEditBox = false
    @State private var showDeleteAlert = false
    @State private var errorMessage: String?
    @State private var toastMessage: String?

    var body: some View {
        Group {
            if let box = box {
                boxContent(box)
            } else if isLoading {
                ProgressView("Loading...")
            } else {
                ContentUnavailableView("Box Not Found", systemImage: "shippingbox.fill",
                                       description: Text("This box may have been deleted."))
            }
        }
        .navigationTitle(box.map { "\($0.roomName) \u{2013} \($0.name)" } ?? "Box")
        .navigationBarTitleDisplayMode(.large)
        .task { await loadBox() }
        .refreshable { await loadBox() }
        .toolbar {
            if let box = box {
                ToolbarItemGroup(placement: .primaryAction) {
                    Menu {
                        Button { showQRCode = true } label: {
                            Label("QR Label", systemImage: "qrcode")
                        }
                        if !box.sealed {
                            Button { showBulkPhoto = true } label: {
                                Label("Bulk Photo Add", systemImage: "camera")
                            }
                        }
                        Divider()
                        if box.sealed {
                            Button { unseal() } label: {
                                Label("Unseal Box", systemImage: "lock.open")
                            }
                        } else {
                            Button { seal() } label: {
                                Label("Seal Box", systemImage: "lock")
                            }
                        }
                        Button { showEditBox = true } label: {
                            Label("Edit Box", systemImage: "pencil")
                        }
                        Divider()
                        Button(role: .destructive) { showDeleteAlert = true } label: {
                            Label("Delete Box", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
        .sheet(isPresented: $showQRCode) {
            if let box = box {
                QRCodeView(box: box)
            }
        }
        .sheet(isPresented: $showBulkPhoto) {
            if let box = box {
                BulkPhotoView(boxId: box.id) { await loadBox() }
            }
        }
        .sheet(isPresented: $showAddItem) {
            if let box = box {
                AddItemView(boxId: box.id) { await loadBox() }
            }
        }
        .sheet(isPresented: $showEditBox) {
            if let box = box {
                EditBoxView(box: box) { await loadBox() }
            }
        }
        .alert("Delete Box?", isPresented: $showDeleteAlert) {
            Button("Delete", role: .destructive) { deleteBox() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will permanently delete the box and all its items.")
        }
        .overlay(alignment: .bottom) {
            if let msg = toastMessage {
                Text(msg)
                    .font(.subheadline.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color(.systemBlue), in: Capsule())
                    .padding(.bottom, 20)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            withAnimation { toastMessage = nil }
                        }
                    }
            }
        }
    }

    @ViewBuilder
    func boxContent(_ box: Box) -> some View {
        List {
            // Box info section
            Section {
                Label(box.roomName, systemImage: "house")
                if !box.notes.isEmpty {
                    Label(box.notes, systemImage: "note.text")
                }
                HStack {
                    Text("Status")
                    Spacer()
                    Text(box.sealed ? "Sealed" : "Open")
                        .font(.subheadline.bold())
                        .foregroundStyle(box.sealed ? .green : .orange)
                }
            }

            // Items section
            Section {
                if box.items.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "tray")
                            .font(.title)
                            .foregroundStyle(.secondary)
                        Text("No items yet")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
                } else {
                    ForEach(box.items) { item in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.name)
                                    .font(.body)
                                HStack(spacing: 8) {
                                    if item.quantity > 1 {
                                        Text("Qty: \(item.quantity)")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    if !item.category.isEmpty {
                                        Text(item.category)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 1)
                                            .background(Color(.systemGray5))
                                            .clipShape(Capsule())
                                    }
                                }
                            }
                            Spacer()
                        }
                        .swipeActions(edge: .trailing) {
                            if !box.sealed {
                                Button(role: .destructive) {
                                    deleteItem(item)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                    }
                }
            } header: {
                HStack {
                    Text("\(box.items.count) Items")
                    Spacer()
                    if !box.sealed {
                        Button("Add Item") { showAddItem = true }
                            .font(.subheadline)
                    }
                }
            }
        }
    }

    func loadBox() async {
        isLoading = true
        defer { isLoading = false }
        do {
            box = try await api.getBox(id: boxId)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func seal() {
        Task {
            do {
                box = try await api.sealBox(id: boxId)
                withAnimation { toastMessage = "Box sealed" }
            } catch {
                withAnimation { toastMessage = error.localizedDescription }
            }
        }
    }

    func unseal() {
        Task {
            do {
                box = try await api.unsealBox(id: boxId)
                withAnimation { toastMessage = "Box unsealed" }
            } catch {
                withAnimation { toastMessage = error.localizedDescription }
            }
        }
    }

    func deleteBox() {
        Task {
            do {
                try await api.deleteBox(id: boxId)
                onDelete?()
                dismiss()
            } catch {
                withAnimation { toastMessage = error.localizedDescription }
            }
        }
    }

    func deleteItem(_ item: Item) {
        Task {
            do {
                try await api.deleteItem(id: item.id)
                await loadBox()
            } catch {
                withAnimation { toastMessage = error.localizedDescription }
            }
        }
    }
}

// MARK: - Edit Box

struct EditBoxView: View {
    let box: Box
    let onSave: () async -> Void

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var notes: String
    @State private var rooms: [Room] = []
    @State private var selectedRoomId: Int

    init(box: Box, onSave: @escaping () async -> Void) {
        self.box = box
        self.onSave = onSave
        _notes = State(initialValue: box.notes)
        _selectedRoomId = State(initialValue: box.roomId)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Text("Box")
                        Spacer()
                        Text(box.name)
                            .foregroundStyle(.secondary)
                    }

                    Picker("Room", selection: $selectedRoomId) {
                        ForEach(rooms) { room in
                            Text(room.name).tag(room.id)
                        }
                    }
                } header: {
                    Text("Box Details")
                } footer: {
                    if selectedRoomId != box.roomId {
                        Text("Moving this box will assign it a new number in the target room.")
                    }
                }

                Section {
                    TextField("Notes", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                } header: {
                    Text("Notes")
                }
            }
            .navigationTitle("Edit Box")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { save() }
                }
            }
            .task {
                do {
                    rooms = try await api.getRooms()
                } catch {}
            }
        }
    }

    func save() {
        Task {
            var data: [String: Any] = [
                "notes": notes.trimmingCharacters(in: .whitespaces),
            ]
            if selectedRoomId != box.roomId {
                data["room_id"] = selectedRoomId
            }
            _ = try? await api.updateBox(id: box.id, data: data)
            await onSave()
            dismiss()
        }
    }
}
