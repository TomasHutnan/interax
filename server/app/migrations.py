"""Applies server/migrations/*.sql in filename order, each exactly once.

Applied versions are recorded in `schema_migrations`. Everything runs in one
transaction under an advisory lock, so concurrent server processes (or the
manage CLI) can't apply the same migration twice, and a failing migration
leaves no partial schema behind.
"""

import logging
from pathlib import Path

from psycopg import Connection
from psycopg.rows import DictRow

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

# Arbitrary, but must stay constant: identifies "the InteraX migration lock".
_LOCK_KEY = 7_340_211


def pending_migrations(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.stem not in applied]


def migrate(conn: Connection[DictRow]) -> list[str]:
    """Applies pending migrations and returns their versions (file stems)."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        done = []
        for path in pending_migrations(applied):
            log.info("applying migration %s", path.name)
            # Bytes, without parameters: psycopg sends it as one simple query,
            # so a file may hold several statements.
            conn.execute(path.read_bytes())
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,)
            )
            done.append(path.stem)
    return done
