import io
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


# ── CORS (allow iOS app to connect) ─────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# ── Models ───────────────────────────────────────────────────────────────────

class Box(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    sealed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    items = db.relationship("Item", backref="box", cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
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


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Box API ──────────────────────────────────────────────────────────────────

@app.route("/api/boxes", methods=["GET"])
def get_boxes():
    boxes = Box.query.order_by(Box.created_at.desc()).all()
    return jsonify([b.to_dict() for b in boxes])


@app.route("/api/boxes", methods=["POST"])
def create_box():
    data = request.json
    box = Box(name=data["name"], location=data.get("location", ""), notes=data.get("notes", ""))
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
    if "name" in data:
        box.name = data["name"]
    if "location" in data:
        box.location = data["location"]
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
    boxes = Box.query.order_by(Box.created_at.desc()).all()
    results = []
    for box in boxes:
        if (q in box.name.lower() or q in box.location.lower()
                or any(q in item.name.lower() for item in box.items)):
            results.append(box.to_dict())
    return jsonify(results)


# ── QR Code ──────────────────────────────────────────────────────────────────

@app.route("/api/boxes/<box_id>/qr", methods=["GET"])
def box_qr(box_id):
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404

    # QR data: a URL that opens the box detail view
    base_url = request.host_url.rstrip("/")
    qr_data = f"{base_url}/?box={box_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"box-{box.name}.png")


@app.route("/api/boxes/<box_id>/qr-label", methods=["GET"])
def box_qr_label(box_id):
    """Return a printable HTML label with QR code, box name, and item summary."""
    box = db.session.get(Box, box_id)
    if not box:
        return jsonify({"error": "Box not found"}), 404
    return render_template("label.html", box=box, base_url=request.host_url.rstrip("/"))


# ── Photo analysis stub ─────────────────────────────────────────────────────

@app.route("/api/analyze-photo", methods=["POST"])
def analyze_photo():
    """Accept an image and return detected items.

    In production this would call a vision AI model. For now it returns a
    helpful prompt so the user can manually enter items detected in the photo.
    """
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400

    # Read and encode the photo for potential future AI integration
    photo = request.files["photo"]
    photo_bytes = photo.read()
    photo_b64 = base64.b64encode(photo_bytes).decode()

    # Return the photo back so the UI can display it for manual item entry
    return jsonify({
        "message": "Photo received. Please review and confirm the items below.",
        "photo_preview": f"data:{photo.content_type};base64,{photo_b64}",
        "detected_items": [],
    })


# ── Bootstrap ────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(debug=True, host="0.0.0.0", port=port)
