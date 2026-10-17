# InteraX Backend (`server/`)

Python backend (FastAPI) powering medication digitization, interaction checks, and ephemeral PIN sessions.

## Responsibilities

- **Vision & Digitization Pipeline:** Ingest pillbox images and handwritten schedules, outputting structured drug regimens.
- **Drug Interaction Engine:** Query pharmacological databases (e.g., open drug databases / interaction APIs) to identify severe contraindications.
- **Ephemeral Session Management:** Generate short, time-limited PINs mapping to anonymous patient data payloads; purge sessions after expiration.
- **API Endpoints:** REST endpoints serving both patient ingestion flow and clinician dashboard data retrieval/updates.

## Tech Stack

- Python 3.11+
- FastAPI & Pydantic
- Package manager: `uv`

## Layout

```
server/
├── app/
│   ├── main.py          # FastAPI app, CORS, DB pool lifespan
│   ├── config.py        # settings, loaded from the repo-root .env
│   ├── db.py            # psycopg connection pool + `get_conn` dependency
│   ├── prescriptions.py # Prescription model + SÚKL lookup + merge
│   └── routers/
│       ├── auth.py      # POST /api/auth/login, /api/auth/logout (dummy)
│       ├── dictate.py   # POST /dictate (audio or transcript -> prescriptions)
│       ├── health.py    # GET  /health
│       ├── medications.py # GET /medications/substances?name=...
│       ├── regimens.py  # GET  /regimens/find?text=..., /regimens/components?name=...
│       ├── scan.py      # POST /scan (auto-detects package vs handwritten)
│       └── uploads.py   # POST /api/uploads, GET|DELETE /api/uploads/{id} (JSON blobs)
└── ocr/                 # OCR modules (OpenAI-compatible vision endpoint)
    ├── auto.py          # classify + extract in one model call
    ├── dictation.py     # local Whisper transcription + text-only medication extraction
    ├── package.py       # dedicated packaging prompt
    └── handwritten.py   # dedicated handwritten-list prompt
```

## Configuration

All settings come from the **repo-root `.env`** (shared with the `db` service; see `.env.example`).

| Variable                                                 | Used for                                                          |
| -------------------------------------------------------- | ----------------------------------------------------------------- |
| `DATABASE_URL`                                           | Postgres connection (required)                                    |
| `CORS_ORIGINS`                                           | Comma-separated allowed origins (default `http://localhost:3000`) |
| `UNSLOTH_BASE_URL` / `UNSLOTH_API_KEY` / `UNSLOTH_MODEL` | OCR model endpoint                                                |
| `WHISPER_MODEL`                                          | Local Whisper model for `/dictate` (default `small`)              |
| `WHISPER_LANGUAGE`                                       | Spoken language (default `cs`; empty = auto-detect)               |

## Running

**With Docker** (from the repo root, API on <http://localhost:8080/docs>):

```sh
docker compose up -d --build
```

**Locally** (DB still in Docker). `DATABASE_URL` in `.env` points at the `db` container,
so override the host/port when running outside Docker; shell variables take precedence
over `.env` and are expanded into `DATABASE_URL`:

```sh
cd server
source serverenv/bin/activate
pip install -r requirements.txt
POSTGRES_HOST=localhost POSTGRES_PORT=5432 uvicorn app.main:app --reload --port 8080
```

Use your `POSTGRES_HOST_PORT` value for `POSTGRES_PORT`. Port 8080 is used because the
OCR model server defaults to 8000.

## `POST /scan`

Multipart form with:

- `file`: the image
- `meds` (required): the current prescription list as a JSON array of `Prescription`
  (`[]` if empty), e.g. `[{"drug":"PRESTARIUM NEO","mg":"5","subs":["PERINDOPRIL ARGININE"],"usage":"1-0-0"}]`

A single model call classifies the image (packaging vs handwritten list) and reads the
medications. Each is matched against SÚKL (`dlp_lecivepripravky` → `dlp_slozeni` → `dlp_latky`)
to get `drug` (product name), `subs` (active substance names) and `mg` (their amounts converted to
mg where possible, `/`-joined in `subs` order, e.g. `"450/50"`); if no product matches, `drug` is
the name as read and `mg`/`subs` are empty.

The result is merged into `meds` and the updated list is returned:

```jsonc
{ "kind": "handwritten", "meds": [{ "drug": "PRESTARIUM NEO", "mg": "5", "subs": ["PERINDOPRIL ARGININE"], "usage": "1-0-1" }, ...] }
```

- A scanned medication is **already present** if its `drug` name matches (case-insensitive).
  Only its `usage` is updated, and only when the image showed one. Substances are not used for
  matching, so different products with the same substance (e.g. generics) stay separate.
- Otherwise it is **appended**. The order of `meds` is preserved.
- Packaging has no dosing, so a package scan only adds the product if it's missing.

`usage` is normalized to one of these notations, or `""` if not written / not recognised:

| Notation  | Meaning                                        |
| --------- | ---------------------------------------------- |
| `a-b-c`   | pieces in the morning, at noon, in the evening |
| `k*`      | k times a day, no set time                     |
| `á n dní` | one piece every n days                         |

## `POST /dictate`

Multipart form with `meds` (as for `/scan`) and exactly one of:

- `file`: an audio recording (webm, m4a, mp3, wav, ...; max 25 MB), transcribed locally by
  Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper), CPU, int8). The Docker
  image bakes in the model; to use another one, build with
  `docker compose build --build-arg WHISPER_MODEL=medium server` (better Czech, ~3x slower).
- `text`: a transcript made elsewhere (e.g. the browser's Web Speech API).

The chat model (text only) then extracts each medication and its usage, in the same notations
as `/scan`. The SÚKL lookup and merge are the same as for `/scan`. Returns the transcript too,
so the user can check what was understood:

```jsonc
{ "transcript": "Prestarium neo pět miligramů jednu ráno...", "meds": [ ... ] }
```

## `GET /medications/substances?name=...`

Best-matching SÚKL product for a free-text name, as a `Prescription` (with `usage: ""`); 404 if
nothing is similar enough.
