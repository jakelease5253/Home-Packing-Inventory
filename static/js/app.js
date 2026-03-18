/* ── PackTrack – Moving Inventory App ──────────────────────────────────── */

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const app = document.getElementById("app");

// ── API helpers ──────────────────────────────────────────────────────────

async function api(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function apiUpload(path, file) {
  const form = new FormData();
  form.append("photo", file);
  const res = await fetch(`/api${path}`, { method: "POST", body: form });
  return res.json();
}

// ── Toast ────────────────────────────────────────────────────────────────

function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Router ───────────────────────────────────────────────────────────────

function navigate(view, params = {}) {
  window.__params = params;
  if (view === "dashboard") renderDashboard();
  else if (view === "room") renderRoomDetail(params.id);
  else if (view === "box") renderBoxDetail(params.id);
}

// Check URL for ?box=<id> (from QR code scan)
function checkDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const boxId = params.get("box");
  if (boxId) {
    navigate("box", { id: boxId });
  } else {
    navigate("dashboard");
  }
}

// ── Dashboard ────────────────────────────────────────────────────────────

async function renderDashboard() {
  const rooms = await api("/rooms");
  const totalBoxes = rooms.reduce((s, r) => s + r.box_count, 0);
  const totalItems = rooms.reduce((s, r) => s + r.item_count, 0);
  const totalSealed = rooms.reduce((s, r) => s + r.sealed_count, 0);
  const roomsWithBoxes = rooms.filter(r => r.box_count > 0);

  app.innerHTML = `
    <div class="stats">
      <div class="stat-card">
        <div class="number">${rooms.length}</div>
        <div class="label">Rooms</div>
      </div>
      <div class="stat-card">
        <div class="number">${totalBoxes}</div>
        <div class="label">Total Boxes</div>
      </div>
      <div class="stat-card">
        <div class="number">${totalItems}</div>
        <div class="label">Total Items</div>
      </div>
      <div class="stat-card">
        <div class="number">${totalSealed}</div>
        <div class="label">Sealed</div>
      </div>
    </div>

    <div class="dashboard-header">
      <div class="search-bar" style="flex:1;max-width:400px;">
        <span class="search-icon">&#128269;</span>
        <input type="text" id="searchInput" placeholder="Search rooms...">
      </div>
      <button class="btn btn-primary" onclick="showCreateBoxModal()">+ New Box</button>
    </div>

    <div class="box-grid" id="boxGrid">
      ${roomsWithBoxes.length === 0 ? `
        <div class="empty-state" style="grid-column:1/-1;">
          <div class="icon">&#127968;</div>
          <p>No rooms with boxes yet. Create your first box to start packing!</p>
        </div>
      ` : roomsWithBoxes.map(r => roomCard(r)).join("")}
    </div>
  `;

  // Search functionality
  const searchInput = $("#searchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const q = searchInput.value.toLowerCase();
      $$(".box-card").forEach(card => {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(q) ? "" : "none";
      });
    });
  }
}

function roomCard(room) {
  const sealedText = room.sealed_count === room.box_count && room.box_count > 0
    ? "All Sealed"
    : room.sealed_count > 0
    ? `${room.sealed_count}/${room.box_count} Sealed`
    : "Open";
  const badgeClass = room.sealed_count === room.box_count && room.box_count > 0
    ? "badge-sealed"
    : "badge-open";

  return `
    <div class="card box-card" onclick="navigate('room',{id:${room.id}})">
      <div class="card-body">
        <div class="box-header">
          <div>
            <div class="box-name">${esc(room.name)}</div>
            <div class="box-location">${room.box_count} box${room.box_count !== 1 ? "es" : ""} &middot; ${room.item_count} item${room.item_count !== 1 ? "s" : ""}</div>
          </div>
          <span class="badge ${badgeClass}">${sealedText}</span>
        </div>
        ${room.box_numbers_display ? `<div style="font-size:.85rem;color:var(--text-light);margin-top:.5rem;">Boxes: ${esc(room.box_numbers_display)}</div>` : ""}
      </div>
    </div>
  `;
}

// ── Room Detail ──────────────────────────────────────────────────────────

async function renderRoomDetail(roomId) {
  const boxes = await api(`/boxes?room_id=${roomId}`);
  const rooms = await api("/rooms");
  const room = rooms.find(r => r.id === roomId);
  const roomName = room ? room.name : "Room";
  const totalItems = boxes.reduce((s, b) => s + b.item_count, 0);
  const sealedCount = boxes.filter(b => b.sealed).length;

  app.innerHTML = `
    <a class="back-link" onclick="navigate('dashboard')">&#8592; All Rooms</a>

    <h2 style="margin:.5rem 0 1rem;">${esc(roomName)}</h2>

    <div class="stats">
      <div class="stat-card">
        <div class="number">${boxes.length}</div>
        <div class="label">Boxes</div>
      </div>
      <div class="stat-card">
        <div class="number">${totalItems}</div>
        <div class="label">Items</div>
      </div>
      <div class="stat-card">
        <div class="number">${sealedCount}</div>
        <div class="label">Sealed</div>
      </div>
      <div class="stat-card">
        <div class="number">${boxes.length - sealedCount}</div>
        <div class="label">Open</div>
      </div>
    </div>

    <div class="dashboard-header">
      <div></div>
      <button class="btn btn-primary" onclick="createBoxInRoom(${roomId})">+ Add Box</button>
    </div>

    <div class="box-grid" id="boxGrid">
      ${boxes.length === 0 ? `
        <div class="empty-state" style="grid-column:1/-1;">
          <div class="icon">&#128230;</div>
          <p>No boxes in this room yet.</p>
        </div>
      ` : boxes.map(b => boxCard(b)).join("")}
    </div>
  `;
}

async function createBoxInRoom(roomId) {
  try {
    const box = await api("/boxes", {
      method: "POST",
      body: { room_id: roomId },
    });
    toast("Box created!", "success");
    navigate("box", { id: box.id });
  } catch (err) {
    toast(err.message, "error");
  }
}

function boxCard(box) {
  const itemPreview = box.items.slice(0, 3).map(i => i.name).join(", ");
  const moreCount = box.items.length > 3 ? ` +${box.items.length - 3} more` : "";
  return `
    <div class="card box-card ${box.sealed ? "sealed" : ""}" onclick="navigate('box',{id:'${box.id}'})">
      <div class="card-body">
        <div class="box-header">
          <div>
            <div class="box-name">${esc(box.name)}</div>
            ${box.notes ? `<div class="box-location">${esc(box.notes)}</div>` : ""}
          </div>
          <span class="badge ${box.sealed ? "badge-sealed" : "badge-open"}">${box.sealed ? "Sealed" : "Open"}</span>
        </div>
        ${itemPreview ? `<div style="font-size:.85rem;color:var(--text-light);margin-top:.5rem;">${esc(itemPreview)}${moreCount}</div>` : ""}
        <div class="box-meta">
          <span class="item-count">${box.item_count} item${box.item_count !== 1 ? "s" : ""}</span>
        </div>
      </div>
    </div>
  `;
}

// ── Create Box Modal ─────────────────────────────────────────────────────

async function showCreateBoxModal() {
  let rooms;
  try {
    rooms = await api("/rooms");
  } catch (err) {
    toast("Failed to load rooms: " + err.message, "error");
    return;
  }

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h2>Create New Box</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Room *</label>
          <select class="form-control" id="newBoxRoom">
            <option value="">Select a room...</option>
            ${rooms.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}
          </select>
        </div>
        <div id="boxNumberPreview" style="font-size:.85rem;color:var(--text-light);margin-bottom:.75rem;"></div>
        <div class="form-group">
          <label>Add Custom Room</label>
          <div style="display:flex;gap:.5rem;">
            <input class="form-control" id="customRoomName" placeholder="e.g. Attic, Basement">
            <button class="btn btn-outline" id="addCustomRoomBtn">Add</button>
          </div>
        </div>
        <div class="form-group">
          <label>Notes</label>
          <textarea class="form-control" id="newBoxNotes" rows="2" placeholder="Fragile, heavy, etc."></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn btn-primary" id="createBoxBtn">Create Box</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  // Update preview when room changes
  const roomSelect = $("#newBoxRoom");
  roomSelect.addEventListener("change", () => {
    const roomId = parseInt(roomSelect.value);
    const room = rooms.find(r => r.id === roomId);
    const preview = $("#boxNumberPreview");
    if (room) {
      const nextNum = (room.box_numbers.length > 0 ? Math.max(...room.box_numbers) + 1 : 1);
      preview.textContent = `This will create Box ${nextNum} in ${room.name}`;
    } else {
      preview.textContent = "";
    }
  });

  // Add custom room
  $("#addCustomRoomBtn").onclick = async () => {
    const name = $("#customRoomName").value.trim();
    if (!name) { toast("Enter a room name", "error"); return; }
    try {
      const room = await api("/rooms", { method: "POST", body: { name } });
      rooms.push(room);
      const opt = document.createElement("option");
      opt.value = room.id;
      opt.textContent = room.name;
      roomSelect.appendChild(opt);
      roomSelect.value = room.id;
      roomSelect.dispatchEvent(new Event("change"));
      $("#customRoomName").value = "";
      toast("Room added!", "success");
    } catch (err) {
      toast(err.message, "error");
    }
  };

  // Handle enter key
  overlay.addEventListener("keydown", e => {
    if (e.key === "Enter") $("#createBoxBtn").click();
  });

  $("#createBoxBtn").onclick = async () => {
    const roomId = parseInt(roomSelect.value);
    if (!roomId) { toast("Please select a room", "error"); return; }
    try {
      const box = await api("/boxes", {
        method: "POST",
        body: { room_id: roomId, notes: $("#newBoxNotes").value.trim() },
      });
      overlay.remove();
      toast("Box created!", "success");
      navigate("box", { id: box.id });
    } catch (err) {
      toast(err.message, "error");
    }
  };
}

// ── Box Detail ───────────────────────────────────────────────────────────

async function renderBoxDetail(boxId) {
  let box;
  try {
    box = await api(`/boxes/${boxId}`);
  } catch {
    toast("Box not found", "error");
    navigate("dashboard");
    return;
  }

  app.innerHTML = `
    <a class="back-link" onclick="navigate('room',{id:${box.room_id}})">&#8592; ${esc(box.room_name)}</a>

    <div class="detail-header">
      <div>
        <div class="detail-title">${esc(box.room_name)} &ndash; ${esc(box.name)} <span class="badge ${box.sealed ? "badge-sealed" : "badge-open"}">${box.sealed ? "Sealed" : "Open"}</span></div>
        ${box.notes ? `<div style="color:var(--text-light);font-size:.85rem;margin-top:.25rem;">${esc(box.notes)}</div>` : ""}
      </div>
      <div class="detail-actions">
        <button class="btn btn-outline btn-sm" onclick="showQRModal('${box.id}')">QR Label</button>
        ${!box.sealed
          ? `<button class="btn btn-outline btn-sm" onclick="showPhotoModal('${box.id}')">Bulk Photo</button>
             <button class="btn btn-accent btn-sm" onclick="sealBox('${box.id}')">Seal Box</button>`
          : `<button class="btn btn-outline btn-sm" onclick="unsealBox('${box.id}')">Unseal</button>`
        }
        <button class="btn btn-danger btn-sm" onclick="deleteBox('${box.id}',${box.room_id})">Delete</button>
      </div>
    </div>

    <div class="card">
      <div class="items-section">
        <div style="padding:0 1rem;">
          <h3>${box.items.length} Item${box.items.length !== 1 ? "s" : ""}</h3>
        </div>
        ${box.items.length === 0 ? `
          <div class="empty-state">
            <div class="icon">&#128722;</div>
            <p>No items yet. Add items manually or use the bulk photo feature.</p>
          </div>
        ` : `
          <ul class="item-list">
            ${box.items.map(item => `
              <li class="item-row">
                <div class="item-info">
                  <span class="item-name">${esc(item.name)}</span>
                  <span class="item-meta">
                    ${item.quantity > 1 ? `Qty: ${item.quantity}` : ""}
                    ${item.category ? ` &middot; ${esc(item.category)}` : ""}
                  </span>
                </div>
                ${!box.sealed ? `
                  <div class="item-actions">
                    <button class="btn btn-outline btn-icon btn-sm" onclick="editItem(${item.id},'${esc(item.name)}',${item.quantity},'${esc(item.category)}','${box.id}')" title="Edit">&#9998;</button>
                    <button class="btn btn-outline btn-icon btn-sm" onclick="deleteItem(${item.id},'${box.id}')" title="Delete">&times;</button>
                  </div>
                ` : ""}
              </li>
            `).join("")}
          </ul>
        `}
      </div>
      ${!box.sealed ? `
        <div class="add-item-form" id="addItemForm">
          <input class="form-control" id="itemName" placeholder="Item name" style="flex:2;">
          <input class="form-control" id="itemQty" type="number" min="1" value="1" placeholder="Qty" style="max-width:70px;">
          <input class="form-control" id="itemCat" placeholder="Category" style="flex:1;">
          <button class="btn btn-primary" onclick="addItem('${box.id}')">Add</button>
        </div>
      ` : ""}
    </div>
  `;

  // Handle enter key in add item form
  const itemName = $("#itemName");
  if (itemName) {
    itemName.addEventListener("keydown", e => {
      if (e.key === "Enter") addItem(box.id);
    });
  }
}

// ── Item CRUD ────────────────────────────────────────────────────────────

async function addItem(boxId) {
  const name = $("#itemName").value.trim();
  if (!name) return;
  const quantity = parseInt($("#itemQty").value) || 1;
  const category = $("#itemCat").value.trim();
  try {
    await api(`/boxes/${boxId}/items`, { method: "POST", body: { name, quantity, category } });
    renderBoxDetail(boxId);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deleteItem(itemId, boxId) {
  if (!confirm("Remove this item?")) return;
  try {
    await api(`/items/${itemId}`, { method: "DELETE" });
    renderBoxDetail(boxId);
  } catch (err) {
    toast(err.message, "error");
  }
}

function editItem(itemId, name, qty, category, boxId) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h2>Edit Item</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Item Name</label>
          <input class="form-control" id="editItemName" value="${esc(name)}">
        </div>
        <div class="form-group">
          <label>Quantity</label>
          <input class="form-control" type="number" id="editItemQty" min="1" value="${qty}">
        </div>
        <div class="form-group">
          <label>Category</label>
          <input class="form-control" id="editItemCat" value="${esc(category)}">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn btn-primary" id="saveItemBtn">Save</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  $("#saveItemBtn").onclick = async () => {
    try {
      await api(`/items/${itemId}`, {
        method: "PUT",
        body: {
          name: $("#editItemName").value.trim(),
          quantity: parseInt($("#editItemQty").value) || 1,
          category: $("#editItemCat").value.trim(),
        },
      });
      overlay.remove();
      renderBoxDetail(boxId);
    } catch (err) {
      toast(err.message, "error");
    }
  };
}

// ── Seal / Unseal / Delete Box ───────────────────────────────────────────

async function sealBox(boxId) {
  if (!confirm("Seal this box? You won't be able to add or modify items until you unseal it.")) return;
  try {
    await api(`/boxes/${boxId}/seal`, { method: "POST" });
    toast("Box sealed!", "success");
    renderBoxDetail(boxId);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function unsealBox(boxId) {
  try {
    await api(`/boxes/${boxId}/unseal`, { method: "POST" });
    toast("Box unsealed", "success");
    renderBoxDetail(boxId);
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deleteBox(boxId, roomId) {
  if (!confirm("Delete this box and all its items? This cannot be undone.")) return;
  try {
    await api(`/boxes/${boxId}`, { method: "DELETE" });
    toast("Box deleted", "success");
    if (roomId) {
      navigate("room", { id: roomId });
    } else {
      navigate("dashboard");
    }
  } catch (err) {
    toast(err.message, "error");
  }
}

// ── QR Code Modal ────────────────────────────────────────────────────────

function showQRModal(boxId) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h2>QR Code Label</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body qr-container">
        <p style="color:var(--text-light);margin-bottom:1rem;">Scan this code to view box contents on any device.</p>
        <img src="/api/boxes/${boxId}/qr" alt="QR Code">
        <div style="margin-top:1rem;display:flex;gap:.5rem;justify-content:center;flex-wrap:wrap;">
          <a class="btn btn-primary" href="/api/boxes/${boxId}/qr" download="box-label-qr.png">Download QR</a>
          <a class="btn btn-accent" href="/api/boxes/${boxId}/qr-label" target="_blank">Print Full Label</a>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}

// ── Bulk Photo Modal ─────────────────────────────────────────────────────

function showPhotoModal(boxId) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal" style="max-width:600px;">
      <div class="modal-header">
        <h2>Bulk Photo Add</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body">
        <p style="color:var(--text-light);margin-bottom:1rem;">
          Take a photo of items you want to add to this box. After uploading, review and edit the item list, then confirm to add them all at once.
        </p>
        <div class="photo-area" id="photoArea">
          <div id="photoPlaceholder">
            <div style="font-size:2.5rem;opacity:.4;">&#128247;</div>
            <p style="margin-top:.5rem;color:var(--text-light);">Click or tap to take a photo / upload an image</p>
          </div>
          <input type="file" accept="image/*" capture="environment" id="photoInput">
          <img id="photoPreview" style="display:none;">
        </div>
        <div id="itemEditor" style="display:none;margin-top:1rem;">
          <h3 style="font-size:.9rem;margin-bottom:.75rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.04em;">Items to Add</h3>
          <p style="font-size:.85rem;color:var(--text-light);margin-bottom:.75rem;">
            Review the photo and list the items you see. Add one item per line.
          </p>
          <div id="bulkItemList"></div>
          <button class="btn btn-outline btn-sm" onclick="addBulkItemRow()" style="margin-top:.5rem;">+ Add Item</button>
        </div>
      </div>
      <div class="modal-footer" id="photoFooter" style="display:none;">
        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn btn-primary" id="confirmBulkBtn">Add All Items</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const photoInput = $("#photoInput");
  const photoPreview = $("#photoPreview");
  const photoPlaceholder = $("#photoPlaceholder");
  const itemEditor = $("#itemEditor");
  const photoFooter = $("#photoFooter");

  photoInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      photoPreview.src = ev.target.result;
      photoPreview.style.display = "block";
      photoPlaceholder.style.display = "none";
    };
    reader.readAsDataURL(file);

    try {
      const result = await apiUpload("/analyze-photo", file);
      itemEditor.style.display = "block";
      photoFooter.style.display = "flex";

      const bulkList = $("#bulkItemList");
      bulkList.innerHTML = "";

      if (result.detected_items && result.detected_items.length > 0) {
        result.detected_items.forEach(item => addBulkItemRow(item.name));
      } else {
        for (let i = 0; i < 3; i++) addBulkItemRow();
      }
    } catch (err) {
      toast("Failed to process photo", "error");
    }
  });

  $("#confirmBulkBtn").onclick = async () => {
    const items = $$('#bulkItemList input[type="text"]')
      .map(input => input.value.trim())
      .filter(name => name.length > 0)
      .map(name => ({ name, quantity: 1 }));

    if (items.length === 0) {
      toast("Add at least one item", "error");
      return;
    }

    try {
      await api(`/boxes/${boxId}/items/bulk`, { method: "POST", body: { items } });
      overlay.remove();
      toast(`${items.length} item${items.length > 1 ? "s" : ""} added!`, "success");
      renderBoxDetail(boxId);
    } catch (err) {
      toast(err.message, "error");
    }
  };
}

function addBulkItemRow(value = "") {
  const list = document.getElementById("bulkItemList");
  const row = document.createElement("div");
  row.className = "detected-item";
  row.innerHTML = `
    <input type="text" class="form-control" value="${esc(value)}" placeholder="Item name">
    <button class="btn btn-icon btn-sm btn-outline" onclick="this.parentElement.remove()" title="Remove">&times;</button>
  `;
  list.appendChild(row);
  const input = row.querySelector("input");
  if (!value) input.focus();
}

// ── Utility ──────────────────────────────────────────────────────────────

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Management: CSV Export ───────────────────────────────────────────────

async function exportInventory() {
  try {
    const boxes = await api("/boxes");
    const rows = [["Room", "Box", "Status", "Notes", "Item Name", "Quantity", "Category"]];
    for (const box of boxes) {
      if (box.items.length === 0) {
        rows.push([box.room_name, box.name, box.sealed ? "Sealed" : "Open", box.notes, "", "", ""]);
      } else {
        for (const item of box.items) {
          rows.push([box.room_name, box.name, box.sealed ? "Sealed" : "Open", box.notes, item.name, item.quantity, item.category]);
        }
      }
    }
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `packtrack-inventory-${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Inventory exported!", "success");
  } catch (err) {
    toast("Export failed: " + err.message, "error");
  }
}

// ── Management: Print All Labels ────────────────────────────────────────

async function printAllLabels() {
  try {
    const boxes = await api("/boxes");
    if (boxes.length === 0) { toast("No boxes to print", "error"); return; }
    const win = window.open("", "_blank");
    win.document.write(`
      <!DOCTYPE html><html><head><title>All Labels</title>
      <style>
        body { font-family: -apple-system, sans-serif; }
        .label { border: 2px solid #000; border-radius: 8px; padding: 1rem; max-width: 360px; margin: 1rem auto; text-align: center; page-break-after: always; }
        .label h2 { margin: 0 0 .25rem; }
        .label .loc { font-size: .9rem; color: #555; margin-bottom: .75rem; }
        .label img { width: 150px; height: 150px; }
        .label ul { text-align: left; font-size: .8rem; margin-top: .5rem; padding-left: 1.2rem; }
        .label .foot { font-size: .65rem; color: #999; margin-top: .5rem; }
        @media print { .no-print { display: none; } }
      </style></head><body>
      <div class="no-print" style="text-align:center;padding:1rem;">
        <button onclick="window.print()" style="padding:.5rem 1.5rem;font-size:1rem;cursor:pointer;">Print All</button>
      </div>
    `);
    for (const box of boxes) {
      const items = box.items.map(i => `<li>${esc(i.name)}${i.quantity > 1 ? ` (x${i.quantity})` : ""}</li>`).join("");
      win.document.write(`
        <div class="label">
          <h2>${esc(box.room_name)} &ndash; ${esc(box.name)}</h2>
          <img src="/api/boxes/${box.id}/qr" alt="QR">
          ${items ? `<ul>${items}</ul>` : ""}
          <div class="foot">Scan QR code to view contents</div>
        </div>
      `);
    }
    win.document.write("</body></html>");
    win.document.close();
  } catch (err) {
    toast("Failed to generate labels: " + err.message, "error");
  }
}

// ── Init ─────────────────────────────────────────────────────────────────

checkDeepLink();
