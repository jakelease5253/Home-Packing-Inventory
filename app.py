import hmac
import io
import os
import base64
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

import qrcode
from flask import Flask, render_template, request, jsonify, send_file

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
_db_url = os.environ.get("DATABASE_URL", "sqlite:///inventory.db")
# Railway Postgres uses postgres:// but SQLAlchemy requires postgresql://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload limit
db = SQLAlchemy(app)

# Store the public URL when ngrok is running
_public_url = None

DEFAULT_ROOMS = [
    "Kitchen", "Living Room", "Master Bedroom", "Bathroom", "Garage",
    "Office", "Dining Room", "Kids Room", "Guest Room", "Laundry Room",
]


# ── API key auth ─────────────────────────────────────────────────────────────
# Set PACKTRACK_API_KEY in the environment to require a shared secret on every
# request. Clients supply it via the X-API-Key header (iOS app), a ?key= query
# param (first web visit, QR scans), or the cookie set after a valid ?key=
# visit. Leave unset for open access during local development.

API_KEY = os.environ.get("PACKTRACK_API_KEY", "")
_KEY_COOKIE = "packtrack_key"


def _valid_key(value):
    return bool(value) and hmac.compare_digest(value, API_KEY)


@app.before_request
def require_api_key():
    if not API_KEY or request.method == "OPTIONS":
        return None
    if request.path.startswith("/static/"):
        return None
    supplied = (
        request.headers.get("X-API-Key")
        or request.args.get("key")
        or request.cookies.get(_KEY_COOKIE)
    )
    if _valid_key(supplied):
        return None
    if request.path == "/":
        return (
            "<h1>PackTrack</h1><p>This server requires an access key. "
            "Open the link you were given with <code>?key=...</code> appended.</p>",
            401,
        )
    return jsonify({"error": "Unauthorized: missing or invalid API key"}), 401


# ── CORS (allow iOS app to connect) ─────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    # Persist a valid ?key= in a cookie so the browser stays authenticated
    # on subsequent page loads and same-origin API calls.
    if API_KEY and _valid_key(request.args.get("key")):
        response.set_cookie(
            _KEY_COOKIE, API_KEY,
            max_age=365 * 24 * 3600, httponly=True, samesite="Lax",
        )
    return response


# ── Models ───────────────────────────────────────────────────────────────────

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_custom = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    boxes = db.relationship("Box", backref="room", lazy=True)

    def to_dict(self):
        box_numbers = sorted([b.number for b in self.boxes])
        return {
            "id": self.id,
            "name": self.name,
            "is_custom": self.is_custom,
            "box_count": len(self.boxes),
            "item_count": sum(i.quantity for b in self.boxes for i in b.items),
            "sealed_count": sum(1 for b in self.boxes if b.sealed),
            "box_numbers": box_numbers,
            "box_numbers_display": _format_number_ranges(box_numbers),
        }


def _format_number_ranges(numbers):
    """Format a list of numbers into ranges like '1-3 & 5-7'."""
    if not numbers:
        return ""
    ranges = []
    start = numbers[0]
    end = numbers[0]
    for n in numbers[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}" if start == end else f"{start}-{end}")
            start = end = n
    ranges.append(f"{start}" if start == end else f"{start}-{end}")
    return " & ".join(ranges)


class Box(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    notes = db.Column(db.Text, default="")
    sealed = db.Column(db.Boolean, default=False)
    label_printed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    items = db.relationship("Item", backref="box", cascade="all, delete-orphan", lazy=True)

    __table_args__ = (db.UniqueConstraint("room_id", "number", name="uq_room_number"),)

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "name": self.name,
            "room_id": self.room_id,
            "room_name": self.room.name if self.room else "",
            # Kept for older clients (the iOS Box model decodes this key)
            "location": self.room.name if self.room else "",
            "notes": self.notes,
            "sealed": self.sealed,
            "label_printed": self.label_printed,
            "created_at": self.created_at.isoformat(),
            "item_count": sum(i.quantity for i in self.items),
            "items": [i.to_dict() for i in self.items],
        }


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    category = db.Column(db.String(80), default="")
    box_id = db.Column(db.String(36), db.ForeignKey("box.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "quantity": self.quantity,
            "category": self.category,
            "box_id": self.box_id,
        }


def _next_box_number(room_id):
    """Find the lowest available box number for a room (fills gaps first)."""
    existing = sorted(
        b.number for b in Box.query.filter_by(room_id=room_id).all()
    )
    # Find first gap
    expected = 1
    for n in existing:
        if n != expected:
            return expected
        expected += 1
    return expected


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Room API ─────────────────────────────────────────────────────────────────

@app.route("/api/rooms", methods=["GET"])
def get_rooms():
    rooms = Room.query.order_by(Room.is_custom, Room.name).all()
    return jsonify([r.to_dict() for r in rooms])


@app.route("/api/rooms", methods=["POST"])
def create_room():
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Room name is required"}), 400
    existing = Room.query.filter(db.func.lower(Room.name) == name.lower()).first()
    if existing:
        return jsonify({"error": "A room with that name already exists"}), 400
    room = Room(name=name, is_custom=True)
    db.session.add(room)
    db.session.commit()
    return jsonify(room.to_dict()), 201


@app.route("/api/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id):
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room.boxes:
        return jsonify({"error": "Cannot delete a room that has boxes. Delete or move the boxes first."}), 400
    db.session.delete(room)
    db.session.commit()
    return jsonify({"ok": True})


# ── Box API ──────────────────────────────────────────────────────────────────

@app.route("/api/boxes", methods=["GET"])
def get_boxes():
    room_id = request.args.get("room_id")
    query = Box.query
    if room_id:
        try:
            room_id = int(room_id)
        except ValueError:
            return jsonify({"error": "room_id must be an integer"}), 400
        query = query.filter_by(room_id=room_id)
    boxes = query.order_by(Box.room_id, Box.number).all()
    return jsonify([b.to_dict() for b in boxes])


@app.route("/api/boxes", methods=["POST"])
def create_box():
    data = request.json
    room_id = data.get("room_id")
    if not room_id:
        return jsonify({"error": "room_id is required"}), 400
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    # Two concurrent creations can pick the same number (read-then-write);
    # the uq_room_number constraint catches it — re-read and retry.
    for _ in range(3):
        number = _next_box_number(room_id)
        box = Box(
            room_id=room_id,
            number=number,
            name=f"Box {number}",
            notes=data.get("notes", ""),
        )
        db.session.add(box)
        try:
            db.session.commit()
            return jsonify(box.to_dict()), 201
        except IntegrityError:
            db.session.rollback()
    return jsonify({"error": "Could not allocate a box number. Please try again."}), 409


@app.route("/api/boxes/<box_id>", methods=["GET"])
def get_box(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    return jsonify(box.to_dict())


@app.route("/api/boxes/<box_id>", methods=["PUT"])
def update_box(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    data = request.json
    moving = "room_id" in data
    if moving:
        new_room = db.session.get(Room, data["room_id"])
        if not new_room:
            return jsonify({"error": "Room not found"}), 404
    # Same read-then-write race as create_box when allocating a number in
    # the new room — retry on the unique-constraint violation.
    for _ in range(3):
        if moving:
            # Allocate before touching the box: assigning room_id first
            # makes autoflush count the box itself in the new room.
            number = _next_box_number(new_room.id)
            box.room_id = new_room.id
            box.number = number
            box.name = f"Box {number}"
        if "notes" in data:
            box.notes = data["notes"]
        if "sealed" in data:
            box.sealed = data["sealed"]
        try:
            db.session.commit()
            return jsonify(box.to_dict())
        except IntegrityError:
            db.session.rollback()
            if not moving:
                break
    return jsonify({"error": "Could not allocate a box number. Please try again."}), 409


@app.route("/api/boxes/mark-printed", methods=["POST"])
def mark_boxes_printed():
    data = request.json
    box_ids = data.get("box_ids", [])
    Box.query.filter(Box.id.in_(box_ids)).update({"label_printed": True}, synchronize_session="fetch")
    db.session.commit()
    return jsonify({"updated": len(box_ids)})


@app.route("/api/boxes/<box_id>", methods=["DELETE"])
def delete_box(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    db.session.delete(box)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/boxes/<box_id>/seal", methods=["POST"])
def seal_box(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    box.sealed = True
    db.session.commit()
    return jsonify(box.to_dict())


@app.route("/api/boxes/<box_id>/unseal", methods=["POST"])
def unseal_box(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    box.sealed = False
    db.session.commit()
    return jsonify(box.to_dict())


# ── Item API ─────────────────────────────────────────────────────────────────

def _coerce_quantity(value):
    """Return the quantity as a positive int, or None if invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or value < 1:
        return None
    return value


def _parse_item_payload(entry):
    """Validate an item dict from a request; returns (fields, error)."""
    if not isinstance(entry, dict):
        return None, "Each item must be an object"
    name = str(entry.get("name") or "").strip()
    if not name:
        return None, "Item name is required"
    quantity = _coerce_quantity(entry.get("quantity", 1))
    if quantity is None:
        return None, "Item quantity must be a positive integer"
    return {"name": name, "quantity": quantity, "category": str(entry.get("category") or "")}, None


@app.route("/api/boxes/<box_id>/items", methods=["POST"])
def add_item(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    if box.sealed:
        return jsonify({"error": "Box is sealed. Unseal it first to add items."}), 400
    fields, error = _parse_item_payload(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    item = Item(box_id=box_id, **fields)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/api/boxes/<box_id>/items/bulk", methods=["POST"])
def add_items_bulk(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    if box.sealed:
        return jsonify({"error": "Box is sealed. Unseal it first to add items."}), 400
    data = request.get_json(silent=True) or {}
    entries = data.get("items", [])
    if not isinstance(entries, list):
        return jsonify({"error": "items must be a list"}), 400
    # Validate everything before inserting anything
    parsed = []
    for i, entry in enumerate(entries):
        fields, error = _parse_item_payload(entry)
        if error:
            return jsonify({"error": f"Item {i + 1}: {error}"}), 400
        parsed.append(fields)
    items = []
    for fields in parsed:
        item = Item(box_id=box_id, **fields)
        db.session.add(item)
        items.append(item)
    db.session.commit()
    return jsonify([i.to_dict() for i in items]), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.box.sealed:
        return jsonify({"error": "Box is sealed"}), 400
    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = str(data["name"] or "").strip()
        if not name:
            return jsonify({"error": "Item name is required"}), 400
        item.name = name
    if "quantity" in data:
        quantity = _coerce_quantity(data["quantity"])
        if quantity is None:
            return jsonify({"error": "Item quantity must be a positive integer"}), 400
        item.quantity = quantity
    if "category" in data:
        item.category = str(data["category"] or "")
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.box.sealed:
        return jsonify({"error": "Box is sealed"}), 400
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ── Stats API ────────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    central = ZoneInfo("America/Chicago")
    boxes = Box.query.order_by(Box.created_at).all()
    items = Item.query.all()

    def to_central_date(dt):
        """Convert a UTC datetime to a Central Time date string."""
        if not dt:
            return "Unknown"
        utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt.astimezone(central).strftime("%Y-%m-%d")

    # Boxes per day (Central Time)
    boxes_by_day = defaultdict(lambda: {"boxes": 0, "items": 0, "sealed": 0})
    for box in boxes:
        day = to_central_date(box.created_at)
        boxes_by_day[day]["boxes"] += 1
        boxes_by_day[day]["items"] += sum(i.quantity for i in box.items)
        if box.sealed:
            boxes_by_day[day]["sealed"] += 1

    # Items per day (Central Time, by when the item was created)
    items_by_day = defaultdict(int)
    for item in items:
        if item.box and item.created_at:
            day = to_central_date(item.created_at)
            items_by_day[day] += item.quantity

    # Sort days chronologically
    sorted_days = sorted(boxes_by_day.keys())
    daily_stats = []
    for day in sorted_days:
        entry = boxes_by_day[day]
        daily_stats.append({
            "date": day,
            "boxes": entry["boxes"],
            "items": entry["items"],
            "sealed": entry["sealed"],
        })

    # Today's stats (Central Time)
    today = datetime.now(central).strftime("%Y-%m-%d")
    today_data = boxes_by_day.get(today, {"boxes": 0, "items": 0, "sealed": 0})

    # This week's stats (last 7 days, Central Time)
    week_boxes = 0
    week_items = 0
    for i in range(7):
        d = (datetime.now(central) - timedelta(days=i)).strftime("%Y-%m-%d")
        if d in boxes_by_day:
            week_boxes += boxes_by_day[d]["boxes"]
            week_items += boxes_by_day[d]["items"]

    return jsonify({
        "daily": daily_stats,
        "today": {"boxes": today_data["boxes"], "items": today_data["items"]},
        "today_date": today,
        "this_week": {"boxes": week_boxes, "items": week_items},
        "total_boxes": len(boxes),
        "total_items": sum(i.quantity for i in items),
    })


# ── Search ───────────────────────────────────────────────────────────────────

@app.route("/api/boxes/search", methods=["GET"])
def search_boxes():
    q = request.args.get("q", "").strip()
    if not q:
        return get_boxes()
    escaped = q.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
    pattern = f"%{escaped}%"
    boxes = (
        Box.query
        .outerjoin(Room, Box.room_id == Room.id)
        .outerjoin(Item, Item.box_id == Box.id)
        .filter(
            db.or_(
                Box.name.ilike(pattern, escape="\\"),
                Room.name.ilike(pattern, escape="\\"),
                Item.name.ilike(pattern, escape="\\"),
            )
        )
        .distinct()
        .order_by(Box.room_id, Box.number)
        .all()
    )
    return jsonify([b.to_dict() for b in boxes])


# ── QR Code ──────────────────────────────────────────────────────────────────

@app.route("/api/boxes/<box_id>/qr", methods=["GET"])
def box_qr(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(_box_link(box_id))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    room_name = box.room.name if box.room else "box"
    return send_file(buf, mimetype="image/png", download_name=f"{room_name}-box-{box.number}.png")


@app.route("/api/boxes/<box_id>/qr-label", methods=["GET"])
def box_qr_label(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    return render_template("label.html", box=box, base_url=request.host_url.rstrip("/"))


def _box_link(box_id):
    """Deep link to a box, including the access key so scanned QR labels work."""
    link = f"{request.host_url.rstrip('/')}/?box={box_id}"
    if API_KEY:
        link += f"&key={API_KEY}"
    return link


def _generate_qr_image(box_id):
    """Generate a QR code as a PIL Image."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(_box_link(box_id))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


@app.route("/print-labels")
def print_labels_page():
    ids = request.args.get("ids", "")
    try:
        copies = int(request.args.get("copies", 2))
        start = int(request.args.get("start", 0))
    except ValueError:
        return jsonify({"error": "copies and start must be integers"}), 400
    if copies < 1 or start < 0:
        return jsonify({"error": "copies must be >= 1 and start must be >= 0"}), 400

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    box_ids = [bid.strip() for bid in ids.split(",") if bid.strip()]
    boxes = Box.query.filter(Box.id.in_(box_ids)).order_by(Box.room_id, Box.number).all()

    # Avery 5164: 2 columns × 3 rows, label 4" × 3.333"
    # Sheet: 8.5" × 11", top margin 0.5", side margin 0.15625", col gap 0.1875"
    page_w, page_h = letter  # 612 × 792 points
    label_w = 4 * inch
    label_h = 3.333 * inch
    margin_top = 0.5 * inch
    margin_left = 0.15625 * inch
    col_gap = 0.1875 * inch

    # Build flat cell list: None = blank, otherwise box object
    cells = [None] * start
    for box in boxes:
        for _ in range(copies):
            cells.append(box)
    # Pad to fill last sheet
    while len(cells) % 6 != 0:
        cells.append(None)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    for idx, box in enumerate(cells):
        pos_on_sheet = idx % 6
        col = pos_on_sheet % 2
        row = pos_on_sheet // 2

        if idx > 0 and pos_on_sheet == 0:
            c.showPage()

        if box is None:
            continue

        # Calculate position (PDF origin is bottom-left)
        x = margin_left + col * (label_w + col_gap)
        y = page_h - margin_top - (row + 1) * label_h

        # Room name
        room_name = box.room.name if box.room else ""
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(x + label_w / 2, y + label_h - 0.4 * inch, room_name)

        # Box name + item count
        item_count = sum(i.quantity for i in box.items)
        box_line = f"{box.name}  •  {item_count} item{'s' if item_count != 1 else ''}"
        c.setFont("Helvetica", 13)
        c.drawCentredString(x + label_w / 2, y + label_h - 0.75 * inch, box_line)

        # QR code
        qr_img = _generate_qr_image(box.id)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        qr_size = 1.6 * inch
        qr_x = x + (label_w - qr_size) / 2
        qr_y = y + 0.25 * inch
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, qr_size, qr_size)

    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", download_name="labels.pdf")


# ── Packing Sticker Sheets (Avery 5164) ────────────────────────────────────

STICKER_TYPES = {
    "fragile": {
        "line1": "FRAGILE",
        "line2": "Handle with Care",
        "color": (0.85, 0.05, 0.05),  # Red
        "filename": "fragile-stickers.pdf",
    },
    "no-stack": {
        "line1": "DO NOT",
        "line2": "STACK",
        "color": (0.05, 0.15, 0.85),  # Blue
        "filename": "do-not-stack-stickers.pdf",
    },
}


@app.route("/print-stickers")
def print_stickers_page():
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    sticker = request.args.get("type", "fragile")
    sheets = max(1, min(20, int(request.args.get("sheets", 1))))
    cfg = STICKER_TYPES.get(sticker, STICKER_TYPES["fragile"])

    page_w, page_h = letter
    label_w = 4 * inch
    label_h = 3.333 * inch
    margin_top = 0.5 * inch
    margin_left = 0.15625 * inch
    col_gap = 0.1875 * inch

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    r, g, b = cfg["color"]

    for sheet_num in range(sheets):
        if sheet_num > 0:
            c.showPage()

        for pos in range(6):
            col = pos % 2
            row = pos // 2
            x = margin_left + col * (label_w + col_gap)
            y = page_h - margin_top - (row + 1) * label_h

            # Draw a rounded border for the sticker
            c.setStrokeColorRGB(r, g, b)
            c.setLineWidth(3)
            c.roundRect(x + 8, y + 8, label_w - 16, label_h - 16, 10)

            # Line 1 - large bold text
            c.setFillColorRGB(r, g, b)
            c.setFont("Helvetica-Bold", 42)
            c.drawCentredString(x + label_w / 2, y + label_h / 2 + 10, cfg["line1"])

            # Line 2 - slightly smaller
            c.setFont("Helvetica-Bold", 28)
            c.drawCentredString(x + label_w / 2, y + label_h / 2 - 30, cfg["line2"])

    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", download_name=cfg["filename"])


# ── Photo analysis via Claude Vision ────────────────────────────────────────

_MAX_ANALYSIS_EDGE = 1568  # px; the API rejects images over ~8000px / ~5 MB


def _prepare_image_for_analysis(photo_bytes: bytes) -> tuple[str, str]:
    """Downscale and re-encode an upload as JPEG for the vision API.

    Phone photos routinely exceed the API's size limits; resizing to
    ~1568px on the long edge keeps requests well under them and cuts
    token cost. Returns (base64_data, media_type).
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(photo_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((_MAX_ANALYSIS_EDGE, _MAX_ANALYSIS_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def _analyze_image_with_claude(image_b64: str, media_type: str) -> list[dict]:
    """Use Claude Vision API to detect items in a photo."""
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        # Simple listing task: skip adaptive thinking so the full token
        # budget goes to the item list.
        thinking={"type": "disabled"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "You are helping someone catalog items for a moving inventory. "
                            "Look at this photo and list every distinct item you can see. "
                            "Return ONLY a JSON array of strings, where each string is a "
                            "short item name (e.g. [\"Blue lamp\", \"Cardboard box\", \"Winter jacket\"]). "
                            "Be specific but concise. Do not include any other text, just the JSON array."
                        ),
                    },
                ],
            }
        ],
    )

    import json

    text = next(b.text for b in message.content if b.type == "text").strip()
    # Handle cases where the model wraps JSON in markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()
    items = json.loads(text)
    return [{"name": name} for name in items if isinstance(name, str)]


@app.route("/api/analyze-photo", methods=["POST"])
def analyze_photo():
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400

    photo = request.files["photo"]
    photo_bytes = photo.read()

    detected = []
    error = None
    try:
        photo_b64, media_type = _prepare_image_for_analysis(photo_bytes)
    except Exception:
        app.logger.exception("Could not decode uploaded photo")
        media_type = photo.content_type or "image/jpeg"
        photo_b64 = base64.b64encode(photo_bytes).decode()
        error = "Could not read the uploaded image."

    if error is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            error = "Photo analysis is not configured (ANTHROPIC_API_KEY is not set)."
        else:
            try:
                detected = _analyze_image_with_claude(photo_b64, media_type)
            except Exception:
                app.logger.exception("Photo analysis failed")
                error = "Photo analysis failed. Check the server logs for details."

    return jsonify({
        "message": "Photo received. Please review and confirm the items below.",
        "photo_preview": f"data:{media_type};base64,{photo_b64}",
        "detected_items": detected,
        "error": error,
    })


# ── Server Info ──────────────────────────────────────────────────────────────

@app.route("/api/server-info", methods=["GET"])
def server_info():
    return jsonify({"public_url": _public_url})


# ── Bootstrap ────────────────────────────────────────────────────────────────

def _seed_rooms():
    """Seed default rooms if the Room table is empty."""
    if Room.query.count() == 0:
        for name in DEFAULT_ROOMS:
            db.session.add(Room(name=name, is_custom=False))
        db.session.commit()


def _migrate_existing_boxes():
    """Assign any boxes that predate rooms to an 'Uncategorized' room.

    (The location-based room inference ran before the location column was
    dropped; any remaining orphans can only be bucketed generically.)
    """
    orphan_boxes = Box.query.filter(
        db.or_(Box.room_id.is_(None), Box.number.is_(None))
    ).all()
    if not orphan_boxes:
        return

    room = Room.query.filter(db.func.lower(Room.name) == "uncategorized").first()
    if not room:
        room = Room(name="Uncategorized", is_custom=True)
        db.session.add(room)
        db.session.flush()
    for box in orphan_boxes:
        box.room_id = room.id
        box.number = _next_box_number(room.id)
        box.name = f"Box {box.number}"
    db.session.commit()


def _migrate_schema():
    """Bring existing tables in line with the current models."""
    import sqlalchemy
    inspector = sqlalchemy.inspect(db.engine)
    if not inspector.has_table("box"):
        return
    box_columns = {col["name"] for col in inspector.get_columns("box")}
    with db.engine.connect() as conn:
        if "label_printed" not in box_columns:
            conn.execute(sqlalchemy.text("ALTER TABLE box ADD COLUMN label_printed BOOLEAN DEFAULT FALSE"))
        if "location" in box_columns:
            # Redundant copy of the room name; to_dict derives it instead
            conn.execute(sqlalchemy.text("ALTER TABLE box DROP COLUMN location"))
        conn.commit()


with app.app_context():
    db.create_all()
    _migrate_schema()
    _seed_rooms()
    _migrate_existing_boxes()

if __name__ == "__main__":
    import sys

    port = 8080
    use_ngrok = False

    args = sys.argv[1:]
    for arg in args:
        if arg == "--public":
            use_ngrok = True
        else:
            try:
                port = int(arg)
            except ValueError:
                pass

    if use_ngrok and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        try:
            from pyngrok import ngrok
            # Kill any leftover ngrok processes first
            ngrok.kill()
            domain = os.environ.get("NGROK_DOMAIN", "packtrack.ngrok.app")
            for arg in args:
                if arg.startswith("--domain="):
                    domain = arg.split("=", 1)[1]
            options = {"addr": port, "bind_tls": True}
            if domain:
                options["hostname"] = domain
            tunnel = ngrok.connect(**options)
            public_url = tunnel.public_url
            _public_url = public_url
            print(f"\n{'='*50}")
            print(f"  Public URL: {public_url}")
            print(f"  Enter this URL in PackTrack app Settings")
            print(f"{'='*50}\n")
        except ImportError:
            print("pyngrok not installed. Run: pip install pyngrok")
            print("Then run: ngrok config add-authtoken <your-token>")
            print("Get a free token at https://dashboard.ngrok.com/signup")
            sys.exit(1)

    # Never enable the Werkzeug debugger when the server is reachable publicly:
    # it can execute arbitrary Python on the host.
    app.run(debug=not use_ngrok, host="0.0.0.0", port=port)
