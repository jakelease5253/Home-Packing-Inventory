import SwiftUI
import CoreImage.CIFilterBuiltins

struct QRCodeView: View {
    let box: Box
    @EnvironmentObject var api: APIService
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    Text("Scan this code to view box contents on any device.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)

                    // QR code generated locally using CoreImage
                    if let qrImage = generateQRCode(from: api.boxDeepLink(boxId: box.id)) {
                        Image(uiImage: qrImage)
                            .interpolation(.none)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 220, height: 220)
                            .padding()
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                            .shadow(color: .black.opacity(0.1), radius: 8)
                    }

                    // Box info summary
                    VStack(spacing: 8) {
                        Text("\(box.roomName) \u{2013} \(box.name)")
                            .font(.title3.bold())
                        Text("\(box.itemCount) item\(box.itemCount == 1 ? "" : "s")")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    // Item list
                    if !box.items.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(box.items) { item in
                                HStack {
                                    Text("• \(item.name)")
                                        .font(.subheadline)
                                    if item.quantity > 1 {
                                        Text("(x\(item.quantity))")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                        .background(Color(.systemGray6))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    // Actions
                    ShareLink(
                        item: generateQRImage(),
                        preview: SharePreview("QR Label – \(box.name)", image: generateQRImage())
                    ) {
                        Label("Share QR Code", systemImage: "square.and.arrow.up")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    if let labelURL = api.webURL("/api/boxes/\(box.id)/qr-label") {
                        Link(destination: labelURL) {
                            Label("Open Printable Label", systemImage: "printer")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .padding()
            }
            .navigationTitle("QR Label")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    func generateQRCode(from string: String) -> UIImage? {
        let context = CIContext()
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(string.utf8)
        filter.correctionLevel = "M"

        guard let outputImage = filter.outputImage else { return nil }

        let scale = 10.0
        let transformed = outputImage.transformed(by: CGAffineTransform(scaleX: scale, y: scale))

        guard let cgImage = context.createCGImage(transformed, from: transformed.extent) else { return nil }
        return UIImage(cgImage: cgImage)
    }

    func generateQRImage() -> Image {
        if let uiImage = generateQRCode(from: api.boxDeepLink(boxId: box.id)) {
            return Image(uiImage: uiImage)
        }
        return Image(systemName: "qrcode")
    }
}
