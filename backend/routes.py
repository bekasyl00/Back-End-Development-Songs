"""MongoDB-backed Songs REST API for the IBM capstone lab."""

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from bson import json_util
from flask import Response, request
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from . import app


def _mongo_uri():
    """Accept the lab's environment variables without logging credentials."""
    if os.environ.get("MONGODB_URI"):
        return os.environ["MONGODB_URI"]

    service = os.environ.get("MONGODB_SERVICE")
    if not service:
        raise RuntimeError("Set MONGODB_SERVICE or MONGODB_URI before starting Songs")
    port = os.environ.get("MONGODB_PORT")
    if port and ":" not in service:
        service = f"{service}:{port}"
    username = os.environ.get("MONGODB_USERNAME")
    password = os.environ.get("MONGODB_PASSWORD")
    if username and password:
        credentials = f"{quote_plus(username)}:{quote_plus(password)}@"
    else:
        credentials = ""
    return f"mongodb://{credentials}{service}"


client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
db = client[os.environ.get("MONGODB_DATABASE", "songs")]

# Keep the original data and existing database contents. A unique index also
# prevents simultaneous POST requests from creating duplicate song IDs.
db.songs.create_index("id", unique=True)
if db.songs.count_documents({}) == 0:
    with (Path(__file__).parent / "data" / "songs.json").open(encoding="utf-8") as source:
        songs_list = json.load(source)
    for song in songs_list:
        db.songs.update_one({"id": song["id"]}, {"$setOnInsert": song}, upsert=True)


def parse_json(data):
    """Convert BSON values, including ObjectId, into JSON-compatible objects."""
    return json.loads(json_util.dumps(data))


def _json_response(data, status=200):
    return Response(json_util.dumps(data), status=status, mimetype="application/json")


def _song_input(*, creating=False):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - {"id", "title", "lyrics"}:
        return None
    if creating and not all(field in data for field in ("id", "title", "lyrics")):
        return None
    if "id" in data and (
        isinstance(data["id"], bool)
        or not isinstance(data["id"], int)
        or not 0 <= data["id"] <= 2**63 - 1
    ):
        return None
    if any(field in data and not isinstance(data[field], str) for field in ("title", "lyrics")):
        return None
    return data


@app.route("/health", methods=["GET"])
def health():
    return _json_response({"status": "OK"})


@app.route("/count", methods=["GET"])
def count():
    return _json_response({"count": db.songs.count_documents({})})


@app.route("/song", methods=["GET"])
def songs():
    return _json_response({"songs": list(db.songs.find({}))})


@app.route("/song/<int:song_id>", methods=["GET"])
def get_song_by_id(song_id):
    song = db.songs.find_one({"id": song_id})
    if song is None:
        return _json_response({"message": "song with id not found"}, 404)
    return _json_response(song)


@app.route("/song", methods=["POST"])
def create_song():
    song = _song_input(creating=True)
    if song is None:
        return _json_response({"message": "a song requires an integer id, title and lyrics"}, 400)
    try:
        result = db.songs.insert_one(song)
    except DuplicateKeyError:
        return _json_response({"Message": f"song with id {song['id']} already present"}, 302)
    return _json_response({"inserted id": result.inserted_id}, 201)


@app.route("/song/<int:song_id>", methods=["PUT"])
def update_song(song_id):
    changes = _song_input()
    if changes is None:
        return _json_response({"message": "a song update must be a JSON object"}, 400)
    if "id" in changes and changes["id"] != song_id:
        return _json_response({"message": "song id must match the URL"}, 400)
    # IDs are stable; partial changes retain all other stored fields.
    changes.pop("id", None)
    song = db.songs.find_one({"id": song_id})
    if song is None:
        return _json_response({"message": "song not found"}, 404)
    if changes:
        result = db.songs.update_one({"id": song_id}, {"$set": changes})
        if result.matched_count == 0:
            return _json_response({"message": "song not found"}, 404)
        song = db.songs.find_one({"id": song_id})
        if song is None:
            return _json_response({"message": "song not found"}, 404)
    return _json_response(song)


@app.route("/song/<int:song_id>", methods=["DELETE"])
def delete_song(song_id):
    result = db.songs.delete_one({"id": song_id})
    if result.deleted_count == 0:
        return _json_response({"message": "song not found"}, 404)
    return Response(status=204)
