import io

import app as packtrack


# ── Auth ─────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_open_when_no_key_configured(self, client):
        assert client.get("/api/rooms").status_code == 200

    def test_requires_key_when_configured(self, client, monkeypatch):
        monkeypatch.setattr(packtrack, "API_KEY", "secret")
        assert client.get("/api/rooms").status_code == 401
        assert client.get("/").status_code == 401

    def test_wrong_key_rejected(self, client, monkeypatch):
        monkeypatch.setattr(packtrack, "API_KEY", "secret")
        r = client.get("/api/rooms", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_header_key_accepted(self, client, monkeypatch):
        monkeypatch.setattr(packtrack, "API_KEY", "secret")
        r = client.get("/api/rooms", headers={"X-API-Key": "secret"})
        assert r.status_code == 200

    def test_query_key_sets_cookie_for_followups(self, client, monkeypatch):
        monkeypatch.setattr(packtrack, "API_KEY", "secret")
        r = client.get("/?key=secret")
        assert r.status_code == 200
        assert "packtrack_key" in (r.headers.get("Set-Cookie") or "")
        # test client carries the cookie forward
        assert client.get("/api/rooms").status_code == 200

    def test_cors_preflight_passes_without_key(self, client, monkeypatch):
        monkeypatch.setattr(packtrack, "API_KEY", "secret")
        assert client.open("/api/rooms", method="OPTIONS").status_code == 200


# ── Rooms ────────────────────────────────────────────────────────────────────

class TestRooms:
    def test_seeded_rooms_listed(self, client):
        rooms = client.get("/api/rooms").get_json()
        assert len(rooms) == len(packtrack.DEFAULT_ROOMS)

    def test_create_room(self, client):
        r = client.post("/api/rooms", json={"name": "Attic"})
        assert r.status_code == 201
        assert r.get_json()["is_custom"] is True

    def test_create_room_requires_name(self, client):
        assert client.post("/api/rooms", json={"name": "  "}).status_code == 400

    def test_create_room_rejects_duplicate(self, client):
        client.post("/api/rooms", json={"name": "Attic"})
        assert client.post("/api/rooms", json={"name": "attic"}).status_code == 400

    def test_delete_room_with_boxes_rejected(self, client, room_id, box):
        assert client.delete(f"/api/rooms/{room_id}").status_code == 400

    def test_delete_empty_room(self, client):
        rid = client.post("/api/rooms", json={"name": "Attic"}).get_json()["id"]
        assert client.delete(f"/api/rooms/{rid}").status_code == 200


# ── Boxes ────────────────────────────────────────────────────────────────────

class TestBoxes:
    def test_create_box_numbers_sequentially(self, client, room_id):
        n1 = client.post("/api/boxes", json={"room_id": room_id}).get_json()["number"]
        n2 = client.post("/api/boxes", json={"room_id": room_id}).get_json()["number"]
        assert (n1, n2) == (1, 2)

    def test_create_box_fills_gaps(self, client, room_id):
        b1 = client.post("/api/boxes", json={"room_id": room_id}).get_json()
        client.post("/api/boxes", json={"room_id": room_id})
        client.delete(f"/api/boxes/{b1['id']}")
        assert client.post("/api/boxes", json={"room_id": room_id}).get_json()["number"] == 1

    def test_create_box_requires_room(self, client):
        assert client.post("/api/boxes", json={}).status_code == 400
        assert client.post("/api/boxes", json={"room_id": 99999}).status_code == 404

    def test_number_collision_retries(self, client, room_id, box, monkeypatch):
        orig = packtrack._next_box_number
        calls = []

        def racy(rid):
            calls.append(rid)
            return box["number"] if len(calls) == 1 else orig(rid)

        monkeypatch.setattr(packtrack, "_next_box_number", racy)
        r = client.post("/api/boxes", json={"room_id": room_id})
        assert r.status_code == 201
        assert r.get_json()["number"] != box["number"]
        assert len(calls) == 2

    def test_get_boxes_validates_room_id(self, client):
        assert client.get("/api/boxes?room_id=abc").status_code == 400

    def test_box_location_is_room_name(self, client, room_id, box):
        room_name = next(
            r["name"] for r in client.get("/api/rooms").get_json() if r["id"] == room_id
        )
        assert box["location"] == room_name
        assert box["room_name"] == room_name

    def test_move_box_to_other_room(self, client, box):
        rid2 = client.post("/api/rooms", json={"name": "Attic"}).get_json()["id"]
        r = client.put(f"/api/boxes/{box['id']}", json={"room_id": rid2})
        assert r.status_code == 200
        moved = r.get_json()
        assert moved["room_id"] == rid2
        assert moved["number"] == 1
        assert moved["location"] == "Attic"

    def test_seal_blocks_item_changes(self, client, box):
        client.post(f"/api/boxes/{box['id']}/seal")
        r = client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp"})
        assert r.status_code == 400
        client.post(f"/api/boxes/{box['id']}/unseal")
        r = client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp"})
        assert r.status_code == 201


# ── Items ────────────────────────────────────────────────────────────────────

class TestItems:
    def test_add_item(self, client, box):
        r = client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp", "quantity": 2})
        assert r.status_code == 201
        assert r.get_json()["quantity"] == 2

    def test_name_required(self, client, box):
        for payload in [{}, {"name": ""}, {"name": "   "}]:
            r = client.post(f"/api/boxes/{box['id']}/items", json=payload)
            assert r.status_code == 400, payload

    def test_no_json_body_is_400_not_500(self, client, box):
        assert client.post(f"/api/boxes/{box['id']}/items").status_code == 400

    def test_quantity_must_be_positive_int(self, client, box):
        for bad in [-1, 0, 1.5, True, "abc"]:
            r = client.post(f"/api/boxes/{box['id']}/items", json={"name": "X", "quantity": bad})
            assert r.status_code == 400, bad
        r = client.post(f"/api/boxes/{box['id']}/items", json={"name": "X", "quantity": "3"})
        assert r.status_code == 201
        assert r.get_json()["quantity"] == 3

    def test_bulk_is_atomic(self, client, box):
        r = client.post(
            f"/api/boxes/{box['id']}/items/bulk",
            json={"items": [{"name": "A"}, {"name": ""}]},
        )
        assert r.status_code == 400
        assert "Item 2" in r.get_json()["error"]
        assert client.get(f"/api/boxes/{box['id']}").get_json()["items"] == []

    def test_bulk_success(self, client, box):
        r = client.post(
            f"/api/boxes/{box['id']}/items/bulk",
            json={"items": [{"name": "A"}, {"name": "B", "quantity": 2}]},
        )
        assert r.status_code == 201
        assert len(r.get_json()) == 2

    def test_update_item_validates(self, client, box):
        iid = client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp"}).get_json()["id"]
        assert client.put(f"/api/items/{iid}", json={"name": ""}).status_code == 400
        assert client.put(f"/api/items/{iid}", json={"quantity": 0}).status_code == 400
        r = client.put(f"/api/items/{iid}", json={"name": "Big lamp", "quantity": 4})
        assert r.status_code == 200
        assert r.get_json() == {**r.get_json(), "name": "Big lamp", "quantity": 4}

    def test_delete_item(self, client, box):
        iid = client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp"}).get_json()["id"]
        assert client.delete(f"/api/items/{iid}").status_code == 200
        assert client.delete(f"/api/items/{iid}").status_code == 404


# ── Search ───────────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_matches_box_name_and_items(self, client, room_id, box):
        client.post(f"/api/boxes/{box['id']}/items", json={"name": "Winter jacket"})
        other = client.post("/api/boxes", json={"room_id": room_id}).get_json()
        client.post(f"/api/boxes/{other['id']}/items", json={"name": "Coffee mug"})

        ids = {b["id"] for b in client.get("/api/boxes/search?q=jacket").get_json()}
        assert ids == {box["id"]}

        ids = {b["id"] for b in client.get("/api/boxes/search?q=box").get_json()}
        assert ids == {box["id"], other["id"]}

    def test_search_case_insensitive(self, client, box):
        client.post(f"/api/boxes/{box['id']}/items", json={"name": "Winter Jacket"})
        assert len(client.get("/api/boxes/search?q=wInTeR").get_json()) == 1

    def test_search_matches_room_name(self, client, room_id, box):
        room_name = next(
            r["name"] for r in client.get("/api/rooms").get_json() if r["id"] == room_id
        )
        ids = {b["id"] for b in client.get(f"/api/boxes/search?q={room_name}").get_json()}
        assert box["id"] in ids

    def test_search_treats_wildcards_literally(self, client, room_id, box):
        client.post(f"/api/boxes/{box['id']}/items", json={"name": "100% cotton shirt"})
        other = client.post("/api/boxes", json={"room_id": room_id}).get_json()
        client.post(f"/api/boxes/{other['id']}/items", json={"name": "Wool socks"})
        results = client.get("/api/boxes/search?q=100%25").get_json()
        assert {b["id"] for b in results} == {box["id"]}

    def test_empty_query_returns_all_boxes(self, client, box):
        # Clearing the search box shows everything
        ids = {b["id"] for b in client.get("/api/boxes/search?q=").get_json()}
        assert box["id"] in ids


# ── Misc endpoints ───────────────────────────────────────────────────────────

class TestMisc:
    def test_stats(self, client, box):
        client.post(f"/api/boxes/{box['id']}/items", json={"name": "Lamp", "quantity": 3})
        r = client.get("/api/stats")
        assert r.status_code == 200

    def test_print_labels_validates_params(self, client):
        assert client.get("/print-labels?ids=x&copies=lots").status_code == 400
        assert client.get("/print-labels?ids=x&copies=0").status_code == 400
        assert client.get("/print-labels?ids=x&start=-1").status_code == 400

    def test_print_labels_returns_pdf(self, client, box):
        r = client.get(f"/print-labels?ids={box['id']}")
        assert r.status_code == 200
        assert r.content_type == "application/pdf"

    def test_qr_code(self, client, box):
        r = client.get(f"/api/boxes/{box['id']}/qr")
        assert r.status_code == 200
        assert r.content_type == "image/png"

    def test_analyze_photo_unconfigured_reports_error(self, client):
        r = client.post(
            "/api/analyze-photo",
            data={"photo": (io.BytesIO(b"notanimage"), "x.jpg")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["error"] is not None
        assert body["detected_items"] == []

    def test_analyze_photo_requires_file(self, client):
        assert client.post("/api/analyze-photo").status_code == 400
