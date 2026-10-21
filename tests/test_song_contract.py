"""Additional API contract checks using the configured, real MongoDB server.

Run against a disposable database, not a production deployment. Fixtures remove
only their randomly allocated song IDs and do not alter the starter songs.
"""

from uuid import uuid4

import pytest

from backend.routes import db


@pytest.fixture()
def song_id():
    value = 2_000_000_000 + uuid4().int % 1_000_000_000
    yield value
    db.songs.delete_one({"id": value})


@pytest.fixture()
def song(client, song_id):
    data = {"id": song_id, "title": "Contract test", "lyrics": "Original lyrics"}
    response = client.post("/song", json=data)
    assert response.status_code == 201
    return data


def test_health_body(client):
    assert client.get("/health").get_json() == {"status": "OK"}


def test_count_matches_database(client):
    response = client.get("/count")
    assert response.status_code == 200
    assert response.get_json() == {"count": db.songs.count_documents({})}


def test_get_songs_serializes_bson(client):
    response = client.get("/song")
    assert response.status_code == 200
    songs = response.get_json()["songs"]
    assert len(songs) == db.songs.count_documents({})
    assert all("$oid" in item["_id"] for item in songs)


def test_get_song(client, song):
    response = client.get(f"/song/{song['id']}")
    assert response.status_code == 200
    result = response.get_json()
    assert all(result[key] == value for key, value in song.items())
    assert "$oid" in result["_id"]


def test_get_missing_song(client, song_id):
    response = client.get(f"/song/{song_id}")
    assert response.status_code == 404
    assert response.get_json() == {"message": "song with id not found"}


def test_post_returns_inserted_bson_id(client, song_id):
    response = client.post("/song", json={"id": song_id, "title": "New", "lyrics": "Song"})
    assert response.status_code == 201
    inserted_id = response.get_json()["inserted id"]["$oid"]
    assert inserted_id == str(db.songs.find_one({"id": song_id})["_id"])


def test_duplicate_id_does_not_insert(client, song):
    before = db.songs.count_documents({})
    response = client.post("/song", json=song)
    assert response.status_code == 302
    assert response.get_json() == {"Message": f"song with id {song['id']} already present"}
    assert db.songs.count_documents({}) == before


def test_put_partial_preserves_id_and_lyrics(client, song):
    response = client.put(f"/song/{song['id']}", json={"title": "Changed"})
    assert response.status_code == 200
    result = response.get_json()
    assert result["id"] == song["id"]
    assert result["lyrics"] == song["lyrics"]
    assert result["title"] == "Changed"
    assert db.songs.find_one({"id": song["id"]})["title"] == "Changed"


def test_put_missing_song(client, song_id):
    response = client.put(f"/song/{song_id}", json={"title": "Changed"})
    assert response.status_code == 404
    assert response.get_json() == {"message": "song not found"}
    assert db.songs.find_one({"id": song_id}) is None


def test_put_matching_id_and_empty_update(client, song):
    for changes in ({"id": song["id"]}, {}):
        response = client.put(f"/song/{song['id']}", json=changes)
        assert response.status_code == 200
        assert response.get_json()["id"] == song["id"]


def test_put_cannot_change_id(client, song):
    response = client.put(f"/song/{song['id']}", json={"id": song["id"] + 1})
    assert response.status_code == 400
    assert db.songs.find_one({"id": song["id"]}) is not None


def test_delete_returns_empty_204_then_404(client, song):
    response = client.delete(f"/song/{song['id']}")
    assert response.status_code == 204
    assert response.data == b""
    assert db.songs.find_one({"id": song["id"]}) is None
    assert client.delete(f"/song/{song['id']}").status_code == 404


@pytest.mark.parametrize("payload", [
    None, [], {}, {"id": True}, {"id": "1"},
    {"id": 1, "title": [], "lyrics": "x"},
    {"id": -1, "title": "Negative", "lyrics": "x"},
    {"id": 2**63, "title": "Overflow", "lyrics": "x"},
])
def test_post_rejects_invalid_song(client, payload):
    response = client.post("/song", json=payload)
    assert response.status_code == 400


def test_put_rejects_malformed_json(client, song):
    response = client.put(f"/song/{song['id']}", data="{", content_type="application/json")
    assert response.status_code == 400
    assert db.songs.find_one({"id": song["id"]})["title"] == song["title"]


@pytest.mark.parametrize("changes", [{"title.part": "x"}, {"$title": "x"}, {"_id": "replacement"}])
def test_put_rejects_non_song_fields(client, song, changes):
    response = client.put(f"/song/{song['id']}", json=changes)
    assert response.status_code == 400
    assert db.songs.find_one({"id": song["id"]})["title"] == song["title"]
