-- Clinician accounts and their sessions, plus revoke tokens for patient uploads.

CREATE TABLE users (
    id                  bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Stored lowercase; the API lowercases input before comparing.
    username            text        NOT NULL UNIQUE CHECK (username ~ '^[a-z0-9._-]{3,64}$'),
    -- argon2id PHC string, see app/passwords.py.
    password_hash       text        NOT NULL,
    role                text        NOT NULL CHECK (role IN ('clinician', 'admin')),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
    -- SHA-256 of the cookie token: a leaked table can't be replayed as cookies.
    token_hash   bytea       PRIMARY KEY,
    user_id      bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL
);
CREATE INDEX sessions_user_id_idx ON sessions (user_id);
CREATE INDEX sessions_expires_at_idx ON sessions (expires_at);

-- Normally created by database/init/06_uploads.sql; repeated so the server
-- doesn't depend on which init scripts the database image ran.
CREATE TABLE IF NOT EXISTS uploads (
    id          text        PRIMARY KEY CHECK (id ~ '^[0-9]{6}$'),
    data        jsonb       NOT NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now()
);
-- SHA-256 of the token the patient's device got when uploading; needed to revoke.
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS revoke_token_hash bytea;
