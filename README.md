# PackTrack – Moving Inventory

Organize and track your belongings when packing for a move. Create boxes, add items, generate QR code labels, and use bulk photo capture to quickly inventory your things.

**Two interfaces:**
- **iOS App** (primary) – native SwiftUI app with camera, QR scanning, and offline-friendly design
- **Web Management Console** – browser-based dashboard for bulk operations, CSV export, and label printing

## Features

| Feature | iOS App | Web Console |
|---------|---------|-------------|
| Create / edit / seal / delete boxes | Yes | Yes |
| Add items with quantity & category | Yes | Yes |
| QR code generation per box | Yes (CoreImage) | Yes (server-side) |
| Scan QR codes to find boxes | Yes (camera) | Via phone scan |
| Bulk photo add | Yes (native camera) | Yes (file upload) |
| Print labels | Share sheet | Print all at once |
| CSV export | — | Yes |
| Search boxes & items | Yes | Yes |
| Seal / unseal boxes | Yes | Yes |

## Quick Start

### 1. Start the server

```bash
pip install -r requirements.txt
python app.py
```

The server runs on `http://0.0.0.0:5000` (accessible from any device on your network).

### 2. Web console

Open `http://<your-ip>:5000` in a browser. Use this for bulk management, printing all QR labels, and exporting your full inventory as CSV.

### 3. iOS app

1. Open `ios/PackTrack` in Xcode (File > Open > select the `ios/PackTrack` folder)
2. In Xcode: File > New > Project > iOS App, then replace the generated source files with the ones in `ios/PackTrack/PackTrack/`
3. Or create a new Xcode project and add all `.swift` files from `ios/PackTrack/PackTrack/` to it
4. Set the deployment target to iOS 17.0+
5. Add the `Info.plist` entries for camera, photo library, and local network permissions
6. Build and run on your device or simulator

**Connect to your server:** In the iOS app, go to the Settings tab and enter your server URL (e.g., `http://192.168.1.100:5000`). Tap "Save & Test" to verify the connection.

## Project Structure

```
├── app.py                          # Flask backend (API + web console)
├── requirements.txt                # Python dependencies
├── static/
│   ├── css/style.css               # Web console styles
│   └── js/app.js                   # Web console JavaScript
├── templates/
│   ├── index.html                  # Web console entry point
│   └── label.html                  # Printable label template
└── ios/PackTrack/PackTrack/        # iOS app source
    ├── PackTrackApp.swift          # App entry point
    ├── ContentView.swift           # Tab bar with deep link handling
    ├── Info.plist                  # Camera & network permissions
    ├── Assets.xcassets/            # App icon & accent color
    ├── Models/
    │   ├── Box.swift               # Box data model
    │   └── Item.swift              # Item data model
    ├── Services/
    │   └── APIService.swift        # Networking layer
    └── Views/
        ├── DashboardView.swift     # Box list with stats & search
        ├── BoxDetailView.swift     # Box contents & actions
        ├── CreateBoxView.swift     # New box form
        ├── AddItemView.swift       # Single item form
        ├── BulkPhotoView.swift     # Camera/photo bulk add
        ├── QRCodeView.swift        # QR code display & share
        ├── QRScannerView.swift     # Live QR code scanner
        └── SettingsView.swift      # Server URL configuration
```

## Tech Stack

- **Backend**: Python / Flask / SQLAlchemy / SQLite
- **Web Console**: Vanilla HTML / CSS / JavaScript
- **iOS App**: SwiftUI / AVFoundation / CoreImage / PhotosUI
- **QR Codes**: python-qrcode (server), CoreImage CIFilter (iOS)
