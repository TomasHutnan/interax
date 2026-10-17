"""Keeps the database schema migrated while the server runs.

A background thread rather than a step in the app lifespan, because:
- at startup the db may still be loading its CSVs for minutes, and the server
  should come up (and report unready on /health) instead of crash-looping;
- on Azure the db has no volume, so after a db restart it comes back empty and
  must be migrated again without restarting the server.

It also creates the optional bootstrap admin whenever the users table is empty.
"""

import logging
import threading

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

from app.migrations import migrate
from app.passwords import hash_password, password_problem
from app.users import ensure_bootstrap_admin, normalize_username, username_problem

log = logging.getLogger(__name__)

_CHECK_SECONDS = 30
_RETRY_SECONDS = 5


class SchemaKeeper:
    def __init__(
        self,
        pool: ConnectionPool[Connection[DictRow]],
        bootstrap_username: str | None = None,
        bootstrap_password: str | None = None,
    ) -> None:
        self._pool = pool
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        # Set while the schema is known to be up to date.
        self.ready = threading.Event()
        self._bootstrap: tuple[str, str] | None = None
        if bootstrap_username and bootstrap_password:
            username = normalize_username(bootstrap_username)
            if problem := username_problem(username) or password_problem(
                bootstrap_password
            ):
                log.error("ignoring the bootstrap admin: %s", problem)
            else:
                self._bootstrap = (username, hash_password(bootstrap_password))

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="schema-keeper", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                self._check()
                self.ready.set()
                wait = _CHECK_SECONDS
            except psycopg.Error as exc:
                if self.ready.is_set():
                    log.warning("database schema check failed: %s", exc)
                else:
                    log.info("database not ready yet (%s); retrying", exc)
                self.ready.clear()
                wait = _RETRY_SECONDS
            self._stopped.wait(wait)

    def _check(self) -> None:
        with self._pool.connection() as conn:
            for version in migrate(conn):
                log.info("applied migration %s", version)
            if self._bootstrap and ensure_bootstrap_admin(conn, *self._bootstrap):
                log.warning(
                    "users table was empty: created bootstrap admin %r",
                    self._bootstrap[0],
                )
