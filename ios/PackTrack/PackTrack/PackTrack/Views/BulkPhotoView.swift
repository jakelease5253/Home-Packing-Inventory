import SwiftUI
import PhotosUI

struct BulkPhotoView: View {
    let boxId: String
    let onComplete: () async -> Void

    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss
    @State private var selectedPhoto: PhotosPickerItem?
    @State private var capturedImage: UIImage?
    @State private var showCamera = false
    @State private var itemNames: [String] = ["", "", ""]
    @State private var isUploading = false
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var photoUploaded = false

    var validItems: [String] {
        itemNames.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Instructions
                    Text("Take a photo of items, then list them below to add to this box in bulk.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    // Photo section
                    if let image = capturedImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 250)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .padding(.horizontal)
                    }

                    HStack(spacing: 12) {
                        Button {
                            showCamera = true
                        } label: {
                            Label("Camera", systemImage: "camera")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)

                        PhotosPicker(selection: $selectedPhoto, matching: .images) {
                            Label("Library", systemImage: "photo.on.rectangle")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding(.horizontal)

                    if isUploading {
                        ProgressView("Analyzing photo...")
                    }

                    // Item list editor
                    if photoUploaded || capturedImage != nil {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Items to Add")
                                .font(.headline)
                                .padding(.horizontal)

                            Text("Review the photo and list each item you see.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .padding(.horizontal)

                            ForEach(itemNames.indices, id: \.self) { index in
                                HStack {
                                    TextField("Item name", text: $itemNames[index])
                                        .textFieldStyle(.roundedBorder)
                                    Button {
                                        itemNames.remove(at: index)
                                    } label: {
                                        Image(systemName: "minus.circle.fill")
                                            .foregroundStyle(.red)
                                    }
                                }
                                .padding(.horizontal)
                            }

                            Button {
                                itemNames.append("")
                            } label: {
                                Label("Add Row", systemImage: "plus")
                                    .font(.subheadline)
                            }
                            .padding(.horizontal)
                        }
                    }

                    if let errorMessage {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                            .padding(.horizontal)
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Bulk Photo Add")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add \(validItems.count) Items") { saveItems() }
                        .disabled(validItems.isEmpty || isSaving)
                }
            }
            .sheet(isPresented: $showCamera) {
                CameraView { image in
                    capturedImage = image
                    uploadImage(image)
                }
            }
            .onChange(of: selectedPhoto) { _, newValue in
                guard let item = newValue else { return }
                Task {
                    if let data = try? await item.loadTransferable(type: Data.self),
                       let image = UIImage(data: data) {
                        capturedImage = image
                        uploadImage(image)
                    }
                }
            }
        }
    }

    func uploadImage(_ image: UIImage) {
        isUploading = true
        Task {
            do {
                let result = try await api.uploadPhoto(image)
                if let analysisError = result.error {
                    errorMessage = analysisError
                }
                if !result.detectedItems.isEmpty {
                    itemNames = result.detectedItems.map(\.name)
                }
                photoUploaded = true
            } catch {
                // Photo upload is optional — still allow manual entry
                errorMessage = "Photo analysis failed: \(error.localizedDescription)"
                photoUploaded = true
            }
            isUploading = false
        }
    }

    func saveItems() {
        isSaving = true
        Task {
            do {
                let items = validItems.map { ItemCreate(name: $0) }
                _ = try await api.addItemsBulk(boxId: boxId, items: items)
                await onComplete()
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSaving = false
            }
        }
    }
}

// MARK: - Camera View (UIKit wrapper)

struct CameraView: UIViewControllerRepresentable {
    let onCapture: (UIImage) -> Void
    @Environment(\.dismiss) var dismiss

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraView
        init(_ parent: CameraView) { self.parent = parent }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage {
                parent.onCapture(image)
            }
            parent.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}
