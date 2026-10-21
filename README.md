# Songs service

Flask and MongoDB REST service built from IBM's
[official starter](https://github.com/ibm-developer-skills-network/hvlga-Back-End-Development-Songs).
The original 20-song dataset, original tests, dependency file and setup script
are preserved. Additional contract tests use a real MongoDB server.

## Run

Use a disposable MongoDB database for development and testing. Configure the lab
database without placing credentials in source code or command screenshots:

```sh
export MONGODB_SERVICE=127.0.0.1:27017
export MONGODB_DATABASE=songs
# Set MONGODB_USERNAME and MONGODB_PASSWORD if authentication is enabled.
# MONGODB_PORT is optional when MONGODB_SERVICE does not already contain a port.
python -m pip install --no-cache-dir Flask==2.1.2 Werkzeug==2.1.2 pymongo pytest requests
FLASK_APP=app python -m flask run --host=0.0.0.0 --port=5000
```

A complete `MONGODB_URI` can be supplied instead. The database defaults to
`songs`; `MONGODB_DATABASE` overrides it. The application does not print the URI.
At startup, an empty collection is seeded from `backend/data/songs.json`; existing
documents are retained. A unique index on `id` prevents duplicate IDs. Restarting
an intentionally emptied collection will seed the 20 starter songs again.

`python app.py` retains the starter's development-server port **8080**. The Flask
CLI command above explicitly uses **5000** for the lab's curl examples.

## API

| Method | Path | Success response |
| --- | --- | --- |
| GET | `/health` | 200, `{"status":"OK"}` |
| GET | `/count` | 200, `{"count":20}` on fresh data |
| GET | `/song` | 200, `{"songs":[...]}` |
| GET | `/song/<id>` | 200, song document |
| POST | `/song` | 201, `{"inserted id":{"$oid":"..."}}` |
| PUT | `/song/<id>` | 200, updated song document |
| DELETE | `/song/<id>` | 204, empty body |

MongoDB ObjectIds are returned as Extended JSON. A missing GET returns 404 with
`{"message":"song with id not found"}`; a missing PUT or DELETE returns 404 with
`{"message":"song not found"}`. A duplicate POST returns the lab's specified 302
and `{"Message":"song with id <id> already present"}`. POST accepts a nonnegative
signed-64-bit integer `id` and string `title` and `lyrics`. These three fields are
the allowed input keys. PUT uses `$set` for partial updates, retains
the existing ID and returns 400 if the body attempts to change that ID.
Malformed JSON and invalid field types return 400.

## Verification

With the same MongoDB environment configured:

```sh
python -m pytest
curl -i localhost:5000/health
curl -i localhost:5000/count
curl -i localhost:5000/song/1
curl -i -X POST localhost:5000/song -H 'Content-Type: application/json' \
  -d '{"id":21,"title":"Demo","lyrics":"Original lyrics"}'
curl -i -X PUT localhost:5000/song/21 -H 'Content-Type: application/json' \
  -d '{"title":"Updated demo"}'
curl -i -X DELETE localhost:5000/song/21
```

The additional tests create random temporary IDs, then remove only those records.
They do not drop the collection or rewrite the supplied dataset. They need a real
MongoDB connection; no in-memory replacement is included.

## AI assistance

Codex implemented the routes, defensive input handling and additional tests, and
prepared this documentation. This is AI-assisted code based on the IBM starter;
it is not represented as independently learner-authored work. See
[AI_ACKNOWLEDGEMENT.md](AI_ACKNOWLEDGEMENT.md). Local verification does not prove
cloud deployment or course submission.
