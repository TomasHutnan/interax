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
│   ├── main.py          # FastAPI app, middleware, lifespan (pool, schema keeper, upload expiry)
│   ├── config.py        # settings, loaded from the repo-root .env
│   ├── db.py            # psycopg connection pool + `get_conn` dependency
│   ├── auth.py          # sessions, `require_user`, login throttle, CSRF guard
│   ├── passwords.py     # argon2id hashing + password rules
│   ├── users.py         # user operations (shared by the CLI and the server)
│   ├── manage.py        # CLI: python -m app.manage create-user ...
│   ├── migrations.py    # applies migrations/*.sql once each
│   ├── schema.py        # background thread keeping the schema migrated
│   ├── prescriptions.py # Prescription model + SÚKL lookup + merge
│   └── routers/
│       ├── auth.py      # POST /api/auth/login, /api/auth/logout, GET /api/auth/me
│       ├── dictate.py   # POST /api/dictate (audio or transcript -> prescriptions)
│       ├── health.py    # GET  /health
│       ├── interactions.py # POST /api/interactions
│       ├── medications.py # GET /api/medications/substances?name=...
│       ├── regimens.py  # GET  /api/regimens/find?text=..., /api/regimens/components?name=...
│       ├── scan.py      # POST /api/scan (auto-detects package vs handwritten)
│       └── uploads.py   # POST /api/uploads, GET|DELETE /api/uploads/{id} (JSON blobs)
├── migrations/          # schema changes owned by the server (users, sessions, ...)
├── tests/               # pytest; `db`-marked tests need TEST_DATABASE_URL
└── ocr/                 # OCR modules (OpenAI-compatible vision endpoint)
    ├── auto.py          # classify + extract in one model call
    ├── dictation.py     # local Whisper transcription + text-only medication extraction
    ├── package.py       # dedicated packaging prompt
    └── handwritten.py   # dedicated handwritten-list prompt
```

## Configuration

All settings come from the **repo-root `.env`** (shared with the `db` service; see `.env.example`).

<<<<<<< HEAD

| Variable                                                 | Used for                                                          |
| -------------------------------------------------------- | ----------------------------------------------------------------- |
| `DATABASE_URL`                                           | Postgres connection (required)                                    |
| `CORS_ORIGINS`                                           | Comma-separated allowed origins (default `http://localhost:3000`) |
| `UNSLOTH_BASE_URL` / `UNSLOTH_API_KEY` / `UNSLOTH_MODEL` | OCR model endpoint                                                |
| `WHISPER_MODEL`                                          | Local Whisper model for `/dictate` (default `small`)              |
| `WHISPER_LANGUAGE`                                       | Spoken language (default `cs`; empty = auto-detect)               |
| =======                                                  |
| Variable                                                 | Used for                                                          |
| -------------------------------------------------------- | ------------------------------                                    |
| `DATABASE_URL`                                           | Postgres connection (required)                                    |
| `UNSLOTH_BASE_URL` / `UNSLOTH_API_KEY` / `UNSLOTH_MODEL` | OCR model endpoint                                                |

> > > > > > > c24bc4fb83b1c081f0b3a5bd7fe49c65b91608ba

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
OCR model server defaults to 8000. Over plain http, also set `SESSION_COOKIE_SECURE=false`
(compose does this for the local stack).

**Tests:**

```sh
pip install -r requirements-dev.txt
pytest                                   # unit tests, no database needed
TEST_DATABASE_URL=postgresql://interax:<password>@localhost:<port>/interax pytest  # + db tests
```

## Auth

Patients are anonymous. Clinicians and admins log in; both roles can currently do the same.

| Route                                                                                                     | Who                                                   |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `POST /api/scan`, `POST /api/dictate`, `POST /api/uploads`                                                | anyone                                                |
| `DELETE /api/uploads/{id}`                                                                                | the uploader (`X-Revoke-Token` header) or a clinician |
| `GET /api/uploads/{id}`, `/api/interactions`, `/api/regimens/*`, `/api/medications/*`, `GET /api/auth/me` | logged-in clinician/admin                             |
| `GET /health`                                                                                             | anyone (503 until the db is reachable and migrated)   |

- **Login** `POST /api/auth/login` `{"username", "password"}` sets an HttpOnly, `SameSite=Lax`
  session cookie (`__Host-interax_session`; `interax_session` when `SESSION_COOKIE_SECURE=false`)
  and returns `{"username", "role"}`. Wrong username and wrong password both give the same 401;
  10 failures per account or 50 per client within 15 minutes give 429 with `Retry-After`.
- **Sessions** are stored server-side (only a SHA-256 of the token) and end after
  `SESSION_TTL` (default 12 h) or `SESSION_IDLE_TTL` without requests (default 1 h), or on
  `POST /api/auth/logout`. Passwords are hashed with argon2id.
- **CSRF:** state-changing requests that carry the session cookie, and login itself, must send
  an `X-Requested-With` header (any value). In Postman, add it to login/logout and clinician writes.
- **Uploads:** `POST /api/uploads` returns `revoke_token` (shown once) and `expires_at`.

Users are managed from the command line (prompts for the password):

```sh
python -m app.manage create-user alice --role clinician   # or --role admin
python -m app.manage set-password alice                   # also ends her sessions
python -m app.manage set-role alice admin
python -m app.manage delete-user alice
python -m app.manage list-users
```

In Docker: `docker compose exec server python -m app.manage ...`; on Azure:
`az containerapp exec -n interax-server -g rg-team89 --command 'python -m app.manage ...'`.

The server owns the tables in `migrations/` (applied automatically at startup, and re-checked
every 30 s, so a recreated db is migrated again). If `BOOTSTRAP_ADMIN_USERNAME` and
`BOOTSTRAP_ADMIN_PASSWORD` are set, that admin is created whenever the users table is empty.

| Variable                                                | Used for                                                                                                                                                             |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSION_TTL` / `SESSION_IDLE_TTL`                      | Session lifetime / idle timeout in seconds (43200 / 3600)                                                                                                            |
| `SESSION_COOKIE_SECURE`                                 | `false` only for local plain-http development (default true)                                                                                                         |
| `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD` | Optional admin created when there are no users                                                                                                                       |
| `SEED_DEV_USERS`                                        | Dev phase: creates the demo clinician `mrnovak` / `abcdef123456` (`DEV_USERS` in `app/users.py`) whenever it's missing. Default true; **set `false` for production** |
| `UPLOAD_TTL`                                            | Seconds an upload lives (default 3600)                                                                                                                               |

## `POST /api/scan`

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
- A package scan also reads dosing instructions a pharmacist wrote on the box by hand (or on a
  sticker) as its `usage`; printed leaflet dosage is ignored. Without such a note, `usage` is `""`
  and an already-present product keeps its usage.

`usage` is normalized to one of these notations, or `""` if not written / not recognised:

| Notation  | Meaning                                                 |
| --------- | ------------------------------------------------------- |
| `a-b-c`   | pieces in the morning, at noon, in the evening          |
| `kx`      | k times a day, no set time (`k*` is normalized to `kx`) |
| `á n dní` | one piece every n days                                  |

## `POST /api/dictate`

Multipart form with `meds` (as for `/api/scan`) and exactly one of:

- `file`: an audio recording (webm, m4a, mp3, wav, ...; max 25 MB), transcribed locally by
  Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper), CPU, int8). The Docker
  image bakes in the model; to use another one, build with
  `docker compose build --build-arg WHISPER_MODEL=medium server` (better Czech, ~3x slower).
- `text`: a transcript made elsewhere (e.g. the browser's Web Speech API).

The chat model (text only) then extracts each medication and its usage, in the same notations
as `/api/scan`. The SÚKL lookup and merge are the same as for `/api/scan`. Returns the transcript too,
so the user can check what was understood:

```jsonc
{ "transcript": "Prestarium neo pět miligramů jednu ráno...", "meds": [ ... ] }
```

## `GET /api/medications/substances?name=...`

Best-matching SÚKL product for a free-text name, as a `Prescription` (with `usage: ""`); 404 if
nothing is similar enough.
