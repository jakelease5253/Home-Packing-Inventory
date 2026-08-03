# PackTrack Code Review Recommendations

Code review of the Home-Packing-Inventory codebase (2026-08-02). Each item below is
intended to become a card on the Origami Kanban board. Priorities: P0 = security/urgent,
P1 = correctness/reliability, P2 = hygiene, P3 = nice-to-have.

---

## P0 — Security

### 1. Add authentication to the API
- **Problem:** The app is deployed publicly (Railway) with no authentication and
  `Access-Control-Allow-Origin: *` (`app.py:33-40`). Anyone with the URL can read the
  full home inventory, delete boxes/rooms/items, and hit `/api/analyze-photo`, which
  spends Anthropic API credits on your key.
- **Suggested fix:** Require a shared secret (header or `?key=` param) checked in a
  Flask `before_request` hook. Bake the key into the iOS app Settings and the web
  frontend. Full user accounts are overkill for a personal app.

### 2. Don't run the Werkzeug debugger on public URLs
- **Problem:** `app.run(debug=True, host="0.0.0.0")` (`app.py:807`) combined with the
  `--public` ngrok mode exposes the Werkzeug interactive debugger to the internet —
  it can execute arbitrary Python.
- **Suggested fix:** `debug=not use_ngrok`, or `debug=False` whenever the server is
  reachable publicly.

---

## P1 — Photo analysis endpoint (three stacked issues)

### 3. Replace the deprecated Claude model
- **Problem:** `_analyze_image_with_claude` uses `claude-sonnet-4-20250514`
  (`app.py:645`), which is deprecated and retires June 15, 2026 — the endpoint will
  silently stop working.
- **Suggested fix:** Switch to `claude-sonnet-5` (documented drop-in replacement), or
  `claude-haiku-4-5` if cheaper/faster is preferred for simple item listing.

### 4. Stop silently swallowing analysis failures
- **Problem:** `analyze_photo` wraps the API call in `except Exception: detected = []`
  (`app.py:695-698`). A bad API key, oversized image, or retired model all look
  identical to "no items found."
- **Suggested fix:** Log with `app.logger.exception(...)` and return an `"error"`
  field so the UI can show "analysis failed" instead of an empty list.

### 5. Downscale photos before sending to the API
- **Problem:** Uploads up to 32 MB are base64'd straight into the API request. The API
  rejects images over ~5 MB / 8000px, so modern phone photos from the web UI will
  frequently fail (then be silently swallowed per item 4).
- **Suggested fix:** Pillow is already installed — resize to ~1568px on the long edge
  and re-encode as JPEG before base64. Also cuts token cost substantially.

---

## P1 — API robustness (each is a 500 waiting to happen)

### 6. Validate `name` in item endpoints
- `add_item` does `data["name"]` (`app.py:303`) — a missing `name` returns a 500
  instead of a 400. Same in `/items/bulk`. Validate and return 400.

### 7. Validate integer query params
- `int(room_id)` in `get_boxes` (`app.py:195`) and `int(request.args.get("copies", 2))`
  / `int(...("start", 0))` in `print_labels_page` (`app.py:497-498`) crash on
  non-numeric input. Wrap in try/except and return 400.

### 8. Handle the box-number race condition
- `_next_box_number` (`app.py:132`) is read-then-write: two concurrent box creations
  in the same room get the same number, and the `uq_room_number` constraint turns one
  into a 500. Possible with gunicorn's multiple workers even with two people packing.
  Catch `IntegrityError` and retry once.

### 9. Validate item `quantity`
- Negative or non-integer quantities are accepted and pollute all the stats. Enforce a
  positive integer.

---

## P2 — Repo hygiene

### 10. Delete the duplicated iOS project tree
- `ios/PackTrack/PackTrack/{Models,Views,Services,...}` and
  `ios/PackTrack/PackTrack/PackTrack/{...}` are byte-identical copies. The nested one
  is staged in git and referenced by the `.xcodeproj`. Delete the outer copy so edits
  can't land in the tree Xcode doesn't build.

### 11. Untrack .DS_Store files
- Several `.DS_Store` files are tracked/staged. Add `.DS_Store` to `.gitignore` and
  `git rm --cached` the tracked ones.

### 12. Commit or discard staged work
- App icon assets and the iOS project are staged but uncommitted.

---

## P3 — Design improvements (nice-to-have)

### 13. Move search into SQL
- `/api/boxes/search` (`app.py:433-445`) loads every box and item into Python for
  substring matching. An `ilike` query with a join is simpler and faster. Related:
  the room/box `to_dict()` methods have N+1 lazy-load patterns — only worth fixing
  if the dashboard feels slow.

### 14. Drop the redundant `Box.location` column
- It's a copy of the room name that `to_dict` overrides with `self.room.name` anyway
  (`app.py:104`). Once `_migrate_existing_boxes` has run everywhere, drop the column
  and the sync code in `create_box`/`update_box`.

### 15. Adopt Flask-Migrate/Alembic for schema changes
- `_migrate_schema` hand-writes `ALTER TABLE` per new column. Fine now; Alembic makes
  each future change a one-liner. Only worth it if the schema keeps evolving.

### 16. Fix the iOS default server URL
- `APIService.swift:18` defaults to `http://localhost:5000` but the server runs on
  8080 — fresh installs fail until Settings is fixed. Also verify Info.plist ATS
  allows the HTTP/ngrok setup actually used.

### 17. Add a basic test suite
- A single pytest file hitting the CRUD endpoints against in-memory SQLite would
  catch most of the 500s in items 6-9 and protect the migration logic during
  refactors.

---

## Suggested first pass
1. Item 1 + 2 (auth, debug off) — closes the biggest hole, ~1 hour.
2. Items 3-5 together — all touch `_analyze_image_with_claude`/`analyze_photo`.
3. Items 10-11 — quick cleanup.
