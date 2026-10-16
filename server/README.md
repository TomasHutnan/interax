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
│   └── routers/
│       ├── health.py    # GET  /health
│       ├── regimens.py  # GET  /regimens/{id}/components
│       └── scan.py      # POST /scan/package, /scan/handwritten (wraps ocr/)
└── ocr/                 # OCR modules (OpenAI-compatible vision endpoint)
```

## Configuration

All settings come from the **repo-root `.env`** (shared with the `db` service; see `.env.example`).

| Variable                                                 | Used for                                                          |
| -------------------------------------------------------- | ----------------------------------------------------------------- |
| `DATABASE_URL`                                           | Postgres connection (required)                                    |
| `CORS_ORIGINS`                                           | Comma-separated allowed origins (default `http://localhost:3000`) |
| `UNSLOTH_BASE_URL` / `UNSLOTH_API_KEY` / `UNSLOTH_MODEL` | OCR model endpoint                                                |

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
