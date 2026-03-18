import io
import os
import base64
import uuid
from datetime import datetime, timezone
from functools import wraps

import qrcode
from flask import Flask, render_template, request, jsonify, send_file

from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload limit
db = SQLAlchemy(app)

# Store the public URL when ngrok is running
_public_url = None

DEFAULT_ROOMS = [
    "Kitchen", "Living Room", "Master Bedroom", "Bathroom", "Garage",
    "Office", "Dining Room", "Kids Room", "Guest Room", "Laundry Room",
]


# ── CORS (allow iOS app to connect) ─────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
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
            "item_count": sum(len(b.items) for b in self.boxes),
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
    location = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    sealed = db.Column(db.Boolean, default=False)
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
            "location": self.room.name if self.room else self.location,
            "notes": self.notes,
            "sealed": self.sealed,
            "created_at": self.created_at.isoformat(),
            "item_count": len(self.items),
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
        query = query.filter_by(room_id=int(room_id))
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
    number = _next_box_number(room_id)
    name = f"Box {number}"
    box = Box(
        room_id=room_id,
        number=number,
        name=name,
        location=room.name,
        notes=data.get("notes", ""),
    )
    db.session.add(box)
    db.session.commit()
    return jsonify(box.to_dict()), 201


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
    if "room_id" in data:
        new_room = db.session.get(Room, data["room_id"])
        if not new_room:
            return jsonify({"error": "Room not found"}), 404
        box.room_id = new_room.id
        box.number = _next_box_number(new_room.id)
        box.name = f"Box {box.number}"
        box.location = new_room.name
    if "notes" in data:
        box.notes = data["notes"]
    if "sealed" in data:
        box.sealed = data["sealed"]
    db.session.commit()
    return jsonify(box.to_dict())


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

@app.route("/api/boxes/<box_id>/items", methods=["POST"])
def add_item(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    if box.sealed:
        return jsonify({"error": "Box is sealed. Unseal it first to add items."}), 400
    data = request.json
    item = Item(
        name=data["name"],
        quantity=data.get("quantity", 1),
        category=data.get("category", ""),
        box_id=box_id,
    )
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
    data = request.json
    items = []
    for entry in data.get("items", []):
        item = Item(
            name=entry["name"],
            quantity=entry.get("quantity", 1),
            category=entry.get("category", ""),
            box_id=box_id,
        )
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
    data = request.json
    if "name" in data:
        item.name = data["name"]
    if "quantity" in data:
        item.quantity = data["quantity"]
    if "category" in data:
        item.category = data["category"]
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


# ── Search ───────────────────────────────────────────────────────────────────

@app.route("/api/boxes/search", methods=["GET"])
def search_boxes():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return get_boxes()
    boxes = Box.query.order_by(Box.room_id, Box.number).all()
    results = []
    for box in boxes:
        room_name = box.room.name.lower() if box.room else ""
        if (q in box.name.lower() or q in room_name
                or any(q in item.name.lower() for item in box.items)):
            results.append(box.to_dict())
    return jsonify(results)


# ── QR Code ──────────────────────────────────────────────────────────────────

@app.route("/api/boxes/<box_id>/qr", methods=["GET"])
def box_qr(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404

    base_url = request.host_url.rstrip("/")
    qr_data = f"{base_url}/?box={box_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
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


# ── Photo analysis via Claude Vision ────────────────────────────────────────

def _analyze_image_with_claude(image_b64: str, media_type: str) -> list[dict]:
    """Use Claude Vision API to detect items in a photo."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
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

    text = message.content[0].text.strip()
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
    media_type = photo.content_type or "image/jpeg"
    photo_bytes = photo.read()
    photo_b64 = base64.b64encode(photo_bytes).decode()

    try:
        detected = _analyze_image_with_claude(photo_b64, media_type)
    except Exception:
        detected = []

    return jsonify({
        "message": "Photo received. Please review and confirm the items below.",
        "photo_preview": f"data:{media_type};base64,{photo_b64}",
        "detected_items": detected,
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
    """Migrate any existing boxes that lack a room_id."""
    orphan_boxes = Box.query.filter(
        db.or_(Box.room_id.is_(None), Box.number.is_(None))
    ).all()
    if not orphan_boxes:
        return

    for box in orphan_boxes:
        # Try to find or create a room matching the box's location
        room_name = box.location.strip() if box.location else "Uncategorized"
        if not room_name:
            room_name = "Uncategorized"
        room = Room.query.filter(db.func.lower(Room.name) == room_name.lower()).first()
        if not room:
            room = Room(name=room_name, is_custom=True)
            db.session.add(room)
            db.session.flush()
        box.room_id = room.id
        box.number = _next_box_number(room.id)
        box.name = f"Box {box.number}"
        box.location = room.name
    db.session.commit()


with app.app_context():
    db.create_all()
    _seed_rooms()
    _migrate_existing_boxes()

if __name__ == "__main__":
    import sys

    port = 5000
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

    app.run(debug=True, host="0.0.0.0", port=port)
