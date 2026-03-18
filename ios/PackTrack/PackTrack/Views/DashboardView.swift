import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var api: APIService
    @State private var boxes: [Box] = []
    @State private var searchText = ""
    @State private var showCreateBox = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @Binding var deepLinkBoxId: String?

    var filteredBoxes: [Box] {
        if searchText.isEmpty { return boxes }
        let q = searchText.lowercased()
        return boxes.filter { box in
            box.name.lowercased().contains(q) ||
            box.location.lowercased().contains(q) ||
            box.items.contains(where: { $0.name.lowercased().contains(q) })
        }
    }

    var totalItems: Int { boxes.reduce(0) { $0 + $1.itemCount } }
    var sealedCount: Int { boxes.filter(\.sealed).count }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Stats row
                HStack(spacing: 12) {
                    StatCard(value: "\(boxes.count)", label: "Boxes")
                    StatCard(value: "\(totalItems)", label: "Items")
                    StatCard(value: "\(sealedCount)", label: "Sealed")
                    StatCard(value: "\(boxes.count - sealedCount)", label: "Open")
                }
                .padding(.horizontal)

                // Box list
                if filteredBoxes.isEmpty && !isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "shippingbox")
                            .font(.system(size: 48))
                            .foregroundStyle(.secondary)
                        if searchText.isEmpty {
                            Text("No boxes yet")
                                .font(.headline)
                            Text("Tap + to create your first box")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        } else {
                            Text("No matches for \"\(searchText)\"")
                                .font(.headline)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 60)
                } else {
                    LazyVStack(spacing: 10) {
                        ForEach(filteredBoxes) { box in
                            NavigationLink(value: box.id) {
                                BoxCardView(box: box)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
        .navigationTitle("PackTrack")
        .searchable(text: $searchText, prompt: "Search boxes or items")
        .navigationDestination(for: String.self) { boxId in
            BoxDetailView(boxId: boxId, onDelete: { loadBoxes() })
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showCreateBox = true
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showCreateBox) {
            CreateBoxView { newBox in
                boxes.insert(newBox, at: 0)
            }
        }
        .refreshable { await refreshBoxes() }
        .task { await refreshBoxes() }
        .onChange(of: deepLinkBoxId) { _, newValue in
            // Deep link handling is done via NavigationLink value matching
        }
        .overlay {
            if isLoading && boxes.isEmpty {
                ProgressView("Loading...")
            }
        }
    }

    func loadBoxes() {
        Task { await refreshBoxes() }
    }

    func refreshBoxes() async {
        isLoading = true
        defer { isLoading = false }
        do {
            boxes = try await api.getBoxes()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let value: String
    let label: String

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2.bold())
                .foregroundStyle(Color(.systemBlue))
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Box Card

struct BoxCardView: View {
    let box: Box

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(box.name)
                        .font(.headline)
                    if !box.location.isEmpty {
                        Text(box.location)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
                Text(box.sealed ? "Sealed" : "Open")
                    .font(.caption2.bold())
                    .textCase(.uppercase)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(box.sealed ? Color.green.opacity(0.2) : Color.yellow.opacity(0.2))
                    .foregroundStyle(box.sealed ? .green : .orange)
                    .clipShape(Capsule())
            }

            if !box.items.isEmpty {
                Text(box.items.prefix(3).map(\.name).joined(separator: ", ")
                     + (box.items.count > 3 ? " +\(box.items.count - 3) more" : ""))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            HStack {
                Label("\(box.itemCount) item\(box.itemCount == 1 ? "" : "s")", systemImage: "tray")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding()
        .background(box.sealed ? Color.green.opacity(0.04) : Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(box.sealed ? Color.green.opacity(0.3) : Color(.separator).opacity(0.3), lineWidth: 1)
        )
    }
}
