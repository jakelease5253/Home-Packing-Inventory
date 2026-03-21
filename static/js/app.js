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
        <div class="number">${roomsWithBoxes.length}</div>
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
          <div style="display:flex;gap:.35rem;align-items:center;">
            <span class="badge ${box.sealed ? "badge-sealed" : "badge-open"}">${box.sealed ? "Sealed" : "Open"}</span>
            ${box.label_printed ? '<span class="badge badge-labeled">Labeled</span>' : ""}
          </div>
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
        <div class="detail-title">${esc(box.room_name)} &ndash; ${esc(box.name)} <span class="badge ${box.sealed ? "badge-sealed" : "badge-open"}">${box.sealed ? "Sealed" : "Open"}</span>${box.label_printed ? ' <span class="badge badge-labeled">Labeled</span>' : ""}</div>
        ${box.notes ? `<div style="color:var(--text-light);font-size:.85rem;margin-top:.25rem;">${esc(box.notes)}</div>` : ""}
      </div>
      <div class="detail-actions">
        <button class="btn btn-outline btn-sm" onclick="printSingleLabel('${box.id}')">Print Label</button>
        <button class="btn btn-outline btn-sm" onclick="showQRModal('${box.id}')">QR Code</button>
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
          <h3>${box.items.reduce((s, i) => s + (i.quantity || 1), 0)} Item${box.items.reduce((s, i) => s + (i.quantity || 1), 0) !== 1 ? "s" : ""}</h3>
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
                    <button class="btn btn-outline btn-icon btn-sm edit-item-btn" data-item-id="${item.id}" data-item-name="${esc(item.name)}" data-item-qty="${item.quantity}" data-item-cat="${esc(item.category)}" data-box-id="${box.id}" title="Edit">&#9998;</button>
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

  // Attach edit item handlers (using data attributes to avoid quote escaping issues)
  $$(".edit-item-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      editItem(
        parseInt(btn.dataset.itemId),
        btn.dataset.itemName,
        parseInt(btn.dataset.itemQty),
        btn.dataset.itemCat,
        btn.dataset.boxId
      );
    });
  });
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

// ── Management: Print Labels (Avery 5164 – 2×3 grid) ───────────────

async function printLabels() {
  let boxes;
  try {
    boxes = await api("/boxes");
  } catch (err) {
    toast("Failed to load boxes: " + err.message, "error");
    return;
  }
  if (boxes.length === 0) { toast("No boxes to print", "error"); return; }
  showLabelSelectModal(boxes);
}

// Print a single box label directly (called from box detail view)
async function printSingleLabel(boxId) {
  let boxes;
  try {
    boxes = await api("/boxes");
  } catch (err) {
    toast("Failed to load box: " + err.message, "error");
    return;
  }
  const box = boxes.find(b => b.id === boxId);
  if (!box) { toast("Box not found", "error"); return; }
  showLabelPositionModal([box]);
}

// Step 1: Select which labels to print
function showLabelSelectModal(boxes) {
  // Group boxes by room
  const rooms = {};
  for (const box of boxes) {
    const room = box.room_name || "Unknown";
    if (!rooms[room]) rooms[room] = [];
    rooms[room].push(box);
  }

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };

  const roomsHtml = Object.entries(rooms).map(([roomName, roomBoxes]) => `
    <div class="label-select-room">
      <label class="label-select-room-header">
        <input type="checkbox" checked data-room="${escHtml(roomName)}" onchange="toggleRoom(this)">
        <span>${escHtml(roomName)}</span>
        <span class="label-select-count">${roomBoxes.length} box${roomBoxes.length !== 1 ? "es" : ""}</span>
      </label>
      <div class="label-select-boxes">
        ${roomBoxes.map(box => {
          const itemCount = box.items.reduce((s, i) => s + (i.quantity || 1), 0);
          return `<label class="label-select-box">
            <input type="checkbox" checked value="${box.id}" class="label-box-cb">
            <span>${escHtml(box.name)}</span>
            ${box.label_printed ? '<span class="badge badge-labeled" style="font-size:.6rem;padding:.1rem .35rem;">Labeled</span>' : ""}
            <span class="label-select-meta">${itemCount} item${itemCount !== 1 ? "s" : ""}</span>
          </label>`;
        }).join("")}
      </div>
    </div>
  `).join("");

  overlay.innerHTML = `
    <div class="modal" style="max-width:500px;">
      <div class="modal-header">
        <h2>Select Labels to Print</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
          <span id="labelSelCount" style="font-size:.85rem;font-weight:600;">${boxes.length} of ${boxes.length} selected</span>
          <div style="display:flex;gap:.5rem;">
            <button class="btn btn-outline btn-sm" onclick="toggleAllLabels(true)">Select All</button>
            <button class="btn btn-outline btn-sm" onclick="toggleAllLabels(false)">Deselect All</button>
          </div>
        </div>
        <div class="label-select-list" id="labelSelectList">
          ${roomsHtml}
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn btn-primary" id="labelNextBtn" onclick="labelSelectNext()">Next</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  window.__allBoxes = boxes;

  // Attach change listeners to update count
  overlay.querySelectorAll(".label-box-cb").forEach(cb => {
    cb.addEventListener("change", updateLabelSelCount);
  });
}

function toggleAllLabels(checked) {
  document.querySelectorAll(".label-box-cb").forEach(cb => { cb.checked = checked; });
  // Also update room checkboxes
  document.querySelectorAll("[data-room]").forEach(cb => { cb.checked = checked; });
  updateLabelSelCount();
}

function toggleRoom(roomCb) {
  const room = roomCb.closest(".label-select-room");
  room.querySelectorAll(".label-box-cb").forEach(cb => { cb.checked = roomCb.checked; });
  updateLabelSelCount();
}

function updateLabelSelCount() {
  const total = document.querySelectorAll(".label-box-cb").length;
  const checked = document.querySelectorAll(".label-box-cb:checked").length;
  const el = document.getElementById("labelSelCount");
  if (el) el.textContent = `${checked} of ${total} selected`;
  const btn = document.getElementById("labelNextBtn");
  if (btn) btn.disabled = checked === 0;

  // Update room checkbox states
  document.querySelectorAll(".label-select-room").forEach(room => {
    const roomCbs = room.querySelectorAll(".label-box-cb");
    const roomChecked = room.querySelectorAll(".label-box-cb:checked");
    const roomHeader = room.querySelector("[data-room]");
    if (roomHeader) {
      roomHeader.checked = roomChecked.length === roomCbs.length;
      roomHeader.indeterminate = roomChecked.length > 0 && roomChecked.length < roomCbs.length;
    }
  });
}

function labelSelectNext() {
  const selectedIds = new Set(
    Array.from(document.querySelectorAll(".label-box-cb:checked")).map(cb => cb.value)
  );
  if (selectedIds.size === 0) { toast("Select at least one label", "error"); return; }
  const selectedBoxes = window.__allBoxes.filter(b => selectedIds.has(b.id));
  document.querySelector(".modal-overlay")?.remove();
  showLabelPositionModal(selectedBoxes);
}

// Avery 5164: 6 labels/sheet, 2 columns × 3 rows
// Label: 4" × 3.333", Sheet: 8.5" × 11"
// Top margin: 0.5", Side margin: 0.15625", No vertical gap, Horizontal gap: 0.1875"

// Step 2: Choose starting position on the Avery sheet
function showLabelPositionModal(boxes) {
  const copies = 2;
  const totalLabels = boxes.length * copies;
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div class="modal" style="max-width:440px;">
      <div class="modal-header">
        <h2>Print Labels – Avery 5164</h2>
        <button class="btn btn-icon" onclick="this.closest('.modal-overlay').remove()">&times;</button>
      </div>
      <div class="modal-body">
        <p style="font-size:.85rem;color:var(--text-light);margin-bottom:1rem;">
          Select the starting position on the label sheet. Labels will fill left-to-right, top-to-bottom from your selection. This lets you reuse partially-used sheets.
        </p>
        <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem;">
          <label style="font-size:.8rem;font-weight:600;white-space:nowrap;">Copies per box:</label>
          <input type="number" id="labelCopies" class="form-control" min="1" max="10" value="${copies}" style="max-width:70px;" onchange="updateLabelSheetCalc()" oninput="updateLabelSheetCalc()">
        </div>
        <p style="font-size:.8rem;margin-bottom:.75rem;font-weight:600;" id="labelTotalInfo">
          ${boxes.length} box${boxes.length !== 1 ? "es" : ""} &times; ${copies} = ${totalLabels} label${totalLabels !== 1 ? "s" : ""} &bull;
          ${Math.ceil(totalLabels / 6)} sheet${Math.ceil(totalLabels / 6) !== 1 ? "s" : ""} needed from position 1
        </p>
        <div class="avery-sheet" id="averySheet">
          ${[0,1,2,3,4,5].map(i => {
            return `<div class="avery-cell${i === 0 ? " selected" : ""}" data-pos="${i}" onclick="selectAveryStart(${i})">
              <div class="avery-pos">${i + 1}</div>
              <div class="avery-hint">${["Top Left","Top Right","Mid Left","Mid Right","Bottom Left","Bottom Right"][i]}</div>
            </div>`;
          }).join("")}
        </div>
        <p style="font-size:.8rem;color:var(--text-light);margin-top:.75rem;" id="sheetCalc">
          Starting at position 1 &rarr; ${Math.ceil(totalLabels / 6)} sheet${Math.ceil(totalLabels / 6) !== 1 ? "s" : ""}
        </p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn btn-primary" onclick="generateAveryLabels()">Print Labels</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  window.__averyBoxes = boxes;
  window.__averyStart = 0;
}

function updateLabelSheetCalc() {
  const copies = Math.max(1, parseInt(document.getElementById("labelCopies").value) || 1);
  const boxes = window.__averyBoxes;
  const totalLabels = boxes.length * copies;
  const pos = window.__averyStart;
  const labelsOnFirstSheet = 6 - pos;
  const remaining = Math.max(0, totalLabels - labelsOnFirstSheet);
  const sheets = 1 + Math.ceil(remaining / 6);
  const totalSheets = totalLabels <= labelsOnFirstSheet ? 1 : sheets;
  document.getElementById("labelTotalInfo").innerHTML =
    `${boxes.length} box${boxes.length !== 1 ? "es" : ""} &times; ${copies} = ${totalLabels} label${totalLabels !== 1 ? "s" : ""} &bull; ${totalSheets} sheet${totalSheets !== 1 ? "s" : ""} needed from position ${pos + 1}`;
  document.getElementById("sheetCalc").innerHTML =
    `Starting at position ${pos + 1} &rarr; ${totalSheets} sheet${totalSheets !== 1 ? "s" : ""}`;
}

function selectAveryStart(pos) {
  window.__averyStart = pos;
  const cells = document.querySelectorAll(".avery-cell");
  cells.forEach((c, i) => {
    c.classList.toggle("selected", i === pos);
    c.classList.toggle("skipped", i < pos);
  });
  updateLabelSheetCalc();
}

function generateAveryLabels() {
  const boxes = window.__averyBoxes;
  const startPos = window.__averyStart;
  const copies = Math.max(1, parseInt(document.getElementById("labelCopies").value) || 1);
  document.querySelector(".modal-overlay")?.remove();

  // Open server-generated PDF directly
  const ids = boxes.map(b => b.id).join(",");
  const url = `/print-labels?ids=${encodeURIComponent(ids)}&copies=${copies}&start=${startPos}`;
  toast("Generating PDF...", "success");
  window.open(url, "_blank");

  // Mark these boxes as label_printed
  api("/boxes/mark-printed", {
    method: "POST",
    body: { box_ids: boxes.map(b => b.id) },
  }).catch(() => {});
}

// HTML escaper for print window (no DOM access to main page's esc())
function escHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ── Init ─────────────────────────────────────────────────────────────────

checkDeepLink();
