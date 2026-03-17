# Xcode Info.plist Configuration

Since Xcode auto-generates Info.plist, do NOT add a separate Info.plist file.
Instead, add these keys via **Xcode > Target > Info tab > Custom iOS Target Properties**:

| Key | Type | Value |
|-----|------|-------|
| Privacy - Camera Usage Description | String | PackTrack needs camera access to take photos of items for bulk adding and to scan QR codes on boxes. |
| Privacy - Photo Library Usage Description | String | PackTrack needs photo library access to select photos of items for bulk adding to boxes. |
| Privacy - Local Network Usage Description | String | PackTrack connects to your local server to sync box and item data. |

Also add this in **Xcode > Target > Info tab** or in your `*.xcodeproj` build settings:

**App Transport Security Settings:**
- Allow Arbitrary Loads: YES
- Allows Local Networking: YES

This allows the app to connect to your local HTTP server.
