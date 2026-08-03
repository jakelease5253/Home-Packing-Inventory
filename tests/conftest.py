import os

# Must be set before app.py is imported — it configures the DB at import time.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("PACKTRACK_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest

import app as packtrack


@pytest.fixture
def client():
    """Test client with a fresh, seeded in-memory database."""
    with packtrack.app.app_context():
        packtrack.db.drop_all()
        packtrack.db.create_all()
        packtrack._seed_rooms()
    return packtrack.app.test_client()


@pytest.fixture
def room_id(client):
    """ID of a seeded room."""
    return client.get("/api/rooms").get_json()[0]["id"]


@pytest.fixture
def box(client, room_id):
    """A freshly created box (as dict)."""
    return client.post("/api/boxes", json={"room_id": room_id}).get_json()
