import SwiftUI

struct CreateBoxView: View {
    var onCreate: ((Box) -> Void)?

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var name = ""
    @State private var location = ""
    @State private var notes = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @FocusState private var nameFieldFocused: Bool

    var body: some View {
        NavigationStack {
            Form {
                Section("Box Details") {
                    TextField("Box Name", text: $name)
                        .focused($nameFieldFocused)
                    TextField("Destination Room", text: $location)
                    TextField("Notes", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
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
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
                }
            }
            .onAppear { nameFieldFocused = true }
        }
    }

    func createBox() {
        isSaving = true
        Task {
            do {
                let box = try await api.createBox(BoxCreate(
                    name: name.trimmingCharacters(in: .whitespaces),
                    location: location.trimmingCharacters(in: .whitespaces),
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
}
