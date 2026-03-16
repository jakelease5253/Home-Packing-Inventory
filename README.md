# PackTrack – Moving Inventory App

A web app for organizing and tracking your belongings when packing for a move. Create boxes, add items, generate QR code labels, and use bulk photo capture to quickly inventory your things.

## Features

- **Box Management** – Create, edit, seal, and delete boxes. Each box has a name, destination room, and notes field.
- **Item Tracking** – Add items to any open box with name, quantity, and category. Edit or remove items at any time before sealing.
- **QR Code Labels** – Generate a QR code for each box. Scan it with any phone to instantly see the box contents. Print full labels with QR code and item summary.
- **Bulk Photo Add** – Take a photo of items, then quickly list them to add to a box all at once.
- **Seal / Unseal** – Mark a box as sealed to lock its contents. Unseal it anytime to make changes.
- **Search** – Filter boxes and items from the dashboard.
- **Deep Links** – QR codes link directly to the box detail view.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

## Tech Stack

- **Backend**: Python / Flask / SQLAlchemy / SQLite
- **Frontend**: Vanilla HTML / CSS / JavaScript (no build step)
- **QR Codes**: python-qrcode + Pillow
