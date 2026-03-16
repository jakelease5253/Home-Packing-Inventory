import SwiftUI
import AVFoundation

struct QRScannerView: View {
    @Binding var scannedBoxId: String?
    @State private var isScanning = true
    @State private var lastScanned: String?
    @State private var navigateToBox = false
    @State private var targetBoxId: String?

    var body: some View {
        ZStack {
            QRScannerRepresentable(onCodeScanned: handleScan)
                .ignoresSafeArea()

            VStack {
                Spacer()

                // Scanning frame overlay
                RoundedRectangle(cornerRadius: 20)
                    .stroke(Color.white.opacity(0.8), lineWidth: 3)
                    .frame(width: 250, height: 250)
                    .background(Color.clear)

                Spacer()

                // Status bar
                VStack(spacing: 8) {
                    if let last = lastScanned {
                        Text("Scanned! Opening box...")
                            .font(.subheadline.bold())
                            .foregroundStyle(.white)
                    } else {
                        Text("Point at a PackTrack QR code")
                            .font(.subheadline)
                            .foregroundStyle(.white)
                    }
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(.ultraThinMaterial)
            }
        }
        .navigationTitle("Scan QR Code")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(isPresented: $navigateToBox) {
            if let boxId = targetBoxId {
                BoxDetailView(boxId: boxId)
            }
        }
    }

    func handleScan(_ code: String) {
        guard lastScanned == nil else { return } // Prevent double-scan

        // Parse the box ID from the URL: http://host/?box=<id>
        if let components = URLComponents(string: code),
           let boxId = components.queryItems?.first(where: { $0.name == "box" })?.value {
            lastScanned = code
            targetBoxId = boxId
            navigateToBox = true

            // Reset after a delay so user can scan again
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                lastScanned = nil
            }
        }
    }
}

// MARK: - AVFoundation QR Scanner

struct QRScannerRepresentable: UIViewControllerRepresentable {
    let onCodeScanned: (String) -> Void

    func makeUIViewController(context: Context) -> ScannerViewController {
        let vc = ScannerViewController()
        vc.onCodeScanned = onCodeScanned
        return vc
    }

    func updateUIViewController(_ uiViewController: ScannerViewController, context: Context) {}
}

class ScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    var onCodeScanned: ((String) -> Void)?
    private var captureSession: AVCaptureSession?

    override func viewDidLoad() {
        super.viewDidLoad()
        setupCamera()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.captureSession?.startRunning()
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        captureSession?.stopRunning()
    }

    private func setupCamera() {
        let session = AVCaptureSession()
        captureSession = session

        guard let device = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: device) else {
            showPlaceholder()
            return
        }

        if session.canAddInput(input) {
            session.addInput(input)
        }

        let output = AVCaptureMetadataOutput()
        if session.canAddOutput(output) {
            session.addOutput(output)
            output.setMetadataObjectsDelegate(self, queue: .main)
            output.metadataObjectTypes = [.qr]
        }

        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.frame = view.bounds
        previewLayer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(previewLayer)
    }

    private func showPlaceholder() {
        let label = UILabel()
        label.text = "Camera not available.\nUse a physical device to scan QR codes."
        label.textAlignment = .center
        label.numberOfLines = 0
        label.textColor = .secondaryLabel
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            label.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 20),
        ])
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput metadataObjects: [AVMetadataObject], from connection: AVCaptureConnection) {
        guard let object = metadataObjects.first as? AVMetadataMachineReadableCodeObject,
              object.type == .qr,
              let value = object.stringValue else { return }
        onCodeScanned?(value)
    }
}
