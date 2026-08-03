import SwiftUI

struct AddItemView: View {
    let boxId: String
    let onAdd: () async -> Void

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var name = ""
    @State private var quantity = 1
    @State private var category = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var addAnother = false
    @FocusState private var nameFieldFocused: Bool

    var body: some View {
        NavigationStack {
            Form {
                Section("Item Details") {
                    TextField("Item Name", text: $name)
                        .focused($nameFieldFocused)
                    Stepper("Quantity: \(quantity)", value: $quantity, in: 1...999)
                    TextField("Category (optional)", text: $category)
                }

                Section {
                    Toggle("Add Another After Save", isOn: $addAnother)
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                }
            }
            .navigationTitle("Add Item")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") { addItem() }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
                }
            }
            .onAppear { nameFieldFocused = true }
        }
    }

    func addItem() {
        isSaving = true
        Task {
            do {
                _ = try await api.addItem(
                    boxId: boxId,
                    item: ItemCreate(
                        name: name.trimmingCharacters(in: .whitespaces),
                        quantity: quantity,
                        category: category.trimmingCharacters(in: .whitespaces)
                    )
                )
                await onAdd()
                if addAnother {
                    name = ""
                    quantity = 1
                    category = ""
                    isSaving = false
                    nameFieldFocused = true
                } else {
                    dismiss()
                }
            } catch {
                errorMessage = error.localizedDescription
                isSaving = false
            }
        }
    }
}
