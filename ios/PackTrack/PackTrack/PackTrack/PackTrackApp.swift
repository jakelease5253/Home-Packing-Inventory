import SwiftUI

@main
struct PackTrackApp: App {
    @StateObject private var api = APIService.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(api)
        }
    }
}
