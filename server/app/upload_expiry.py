"""Deletes each upload once UPLOAD_TTL has passed since it was created.

Every new upload gets a one-off timer on the server's event loop. Timers live in
memory, so on startup all existing uploads are re-scheduled (already expired
ones fire immediately). Assumes a single server process, which is how it's
deployed; extra processes would only cause redundant, harmless deletes.

Reads must still filter on age: a timer can be late (restart, db down).
"""

import asyncio
import logging
import threading
from datetime import UTC, datetime, timedelta

import psycopg
from fastapi import Request
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

_RETRY_SECONDS = 10

_Key = tuple[str, datetime]


class UploadExpiry:
    def __init__(
        self, pool: ConnectionPool[Connection[DictRow]], ttl: timedelta
    ) -> None:
        self._pool = pool
        self._ttl = ttl
        self._loop: asyncio.AbstractEventLoop | None = None
        self._timers: dict[_Key, asyncio.TimerHandle] = {}
        self._stopped = threading.Event()

    def start(self) -> None:
        """Call from the running event loop (the app lifespan)."""
        self._loop = asyncio.get_running_loop()
        self._loop.run_in_executor(None, self._reschedule_existing)

    def stop(self) -> None:
        self._stopped.set()
        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()

    def schedule(self, upload_id: str, uploaded_at: datetime) -> None:
        """Thread-safe, so sync route handlers can call it."""
        assert self._loop is not None, "UploadExpiry.start() was not called"
        self._loop.call_soon_threadsafe(self._add_timer, upload_id, uploaded_at)

    def _add_timer(
        self, upload_id: str, uploaded_at: datetime, delay: float | None = None
    ) -> None:
        if self._stopped.is_set():
            return
        key = (upload_id, uploaded_at)
        if key in self._timers:
            return
        if delay is None:
            remaining = uploaded_at + self._ttl - datetime.now(UTC)
            delay = max(remaining.total_seconds(), 0.0)
        assert self._loop is not None
        self._timers[key] = self._loop.call_later(delay, self._fire, key)

    def _fire(self, key: _Key) -> None:
        self._timers.pop(key, None)
        if not self._stopped.is_set():
            assert self._loop is not None
            self._loop.run_in_executor(None, self._delete, *key)

    def _delete(self, upload_id: str, uploaded_at: datetime) -> None:
        try:
            # Matching uploaded_at too: if the code was freed and reused by a newer
            # upload, that one has its own timer and must survive this one.
            with self._pool.connection() as conn:
                conn.execute(
                    "DELETE FROM uploads WHERE id = %s AND uploaded_at = %s",
                    (upload_id, uploaded_at),
                )
        except psycopg.Error:
            if self._stopped.is_set():
                return
            log.exception(
                "deleting expired upload %s failed; retrying in %ss",
                upload_id,
                _RETRY_SECONDS,
            )
            assert self._loop is not None
            self._loop.call_soon_threadsafe(
                self._add_timer, upload_id, uploaded_at, _RETRY_SECONDS
            )

    def _reschedule_existing(self) -> None:
        # The db may still be starting (e.g. loading CSVs), so keep trying.
        while not self._stopped.is_set():
            try:
                with self._pool.connection() as conn:
                    rows = conn.execute(
                        "SELECT id, uploaded_at FROM uploads"
                    ).fetchall()
            except psycopg.Error as exc:
                log.warning(
                    "could not load uploads to expire (%s); retrying in %ss",
                    exc,
                    _RETRY_SECONDS,
                )
                self._stopped.wait(_RETRY_SECONDS)
                continue
            for row in rows:
                self.schedule(row["id"], row["uploaded_at"])
            log.info("scheduled expiry for %d existing upload(s)", len(rows))
            return


def get_upload_expiry(request: Request) -> UploadExpiry:
    return request.app.state.upload_expiry
