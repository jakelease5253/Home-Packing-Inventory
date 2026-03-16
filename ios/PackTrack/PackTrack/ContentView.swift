import SwiftUI

struct ContentView: View {
    @State private var deepLinkBoxId: String?

    var body: some View {
        TabView {
            NavigationStack {
                DashboardView(deepLinkBoxId: $deepLinkBoxId)
            }
            .tabItem {
                Label("Boxes", systemImage: "shippingbox")
            }

            NavigationStack {
                QRScannerView(scannedBoxId: $deepLinkBoxId)
            }
            .tabItem {
                Label("Scan", systemImage: "qrcode.viewfinder")
            }

            NavigationStack {
                SettingsView()
            }
            .tabItem {
                Label("Settings", systemImage: "gear")
            }
        }
        .tint(Color("AccentColor"))
        .onOpenURL { url in
            // Handle deep links from QR codes: packtrack://box/<id> or http://host/?box=<id>
            if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
               let boxParam = components.queryItems?.first(where: { $0.name == "box" })?.value {
                deepLinkBoxId = boxParam
            }
        }
    }
}
