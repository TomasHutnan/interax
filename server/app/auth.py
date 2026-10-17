"""Clinician sessions.

A session is an opaque random token in an HttpOnly cookie; the database only
stores its SHA-256, so the sessions table can't be replayed as cookies. A
session ends at `expires_at` (SESSION_TTL after login) or after
SESSION_IDLE_TTL without requests, whichever comes first, and on logout.

CSRF: the cookie is SameSite=Lax, and every state-changing request that
carries it (plus login itself) must also send the `X-Requested-With` header.
Browsers only let a page add custom headers cross-origin after a CORS
preflight, and the API never allows credentialed cross-origin requests, so a
foreign page can't produce a request that has both the cookie and the header.
"""

import hashlib
import logging
import math
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from psycopg import Connection
from psycopg.rows import DictRow

from app.config import settings
from app.users import Role

log = logging.getLogger(__name__)

# The __Host- prefix makes browsers reject the cookie unless it's Secure, has
# Path=/ and no Domain, so no other (sub)domain can set or shadow it.
SESSION_COOKIE = (
    "__Host-interax_session" if settings.session_cookie_secure else "interax_session"
)
CSRF_HEADER = "X-Requested-With"
LOGIN_PATH = "/api/auth/login"

# last_seen_at is written at most this often per session, not on every request.
_TOUCH_INTERVAL = timedelta(minutes=1)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: Role


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def create_session(conn: Connection[DictRow], user_id: int) -> str:
    """Stores a new session and returns its token (for the cookie)."""
    token = new_token()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at)"
        " VALUES (%s, %s, now() + %s)",
        (hash_token(token), user_id, settings.session_ttl),
    )
    return token


def delete_session(conn: Connection[DictRow], token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = %s", (hash_token(token),))


def delete_expired_sessions(conn: Connection[DictRow]) -> None:
    conn.execute(
        "DELETE FROM sessions WHERE expires_at <= now() OR last_seen_at <= now() - %s",
        (settings.session_idle_ttl,),
    )


def session_user(conn: Connection[DictRow], token: str) -> User | None:
    """The user the token belongs to, if the session is still valid."""
    token_hash = hash_token(token)
    row = conn.execute(
        """
        SELECT u.id, u.username, u.role,
               s.last_seen_at < now() - %(touch)s AS stale
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %(hash)s
          AND s.expires_at > now()
          AND s.last_seen_at > now() - %(idle)s
        """,
        {
            "hash": token_hash,
            "touch": _TOUCH_INTERVAL,
            "idle": settings.session_idle_ttl,
        },
    ).fetchone()
    if row is None:
        return None
    if row["stale"]:
        conn.execute(
            "UPDATE sessions SET last_seen_at = now() WHERE token_hash = %s",
            (token_hash,),
        )
    return User(id=row["id"], username=row["username"], role=row["role"])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(settings.session_ttl.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def optional_user(request: Request) -> User | None:
    """The logged-in user, or None. Uses its own short-lived db connection."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with request.app.state.pool.connection() as conn:
        return session_user(conn, token)


def require_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    """Any logged-in clinician or admin; 401 otherwise."""
    if user is None:
        raise HTTPException(status_code=401, detail="not logged in")
    return user


class Throttle:
    """Counts failures per key within a sliding window.

    In memory: correct for the single server process this runs as; with more
    processes each would allow its own `max_failures`.
    """

    def __init__(
        self,
        max_failures: int,
        window: timedelta,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window.total_seconds()
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float] | None:
        failures = self._failures.get(key)
        if failures is None:
            return None
        while failures and failures[0] <= now - self._window:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return None
        return failures

    def retry_after(self, key: str) -> float:
        """Seconds until `key` may try again; 0 if it may now."""
        with self._lock:
            now = self._clock()
            failures = self._prune(key, now)
            if failures is None or len(failures) < self._max:
                return 0.0
            return failures[-self._max] + self._window - now

    def fail(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._prune(key, now)
            self._failures.setdefault(key, deque()).append(now)
            # Bound memory under a flood of distinct keys.
            if len(self._failures) > 10_000:
                for stale in list(self._failures):
                    self._prune(stale, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def retry_after_header(seconds: float) -> dict[str, str]:
    return {"Retry-After": str(max(1, math.ceil(seconds)))}


async def security_middleware(request: Request, call_next):
    """CSRF check for cookie-authenticated writes; no caching of API responses."""
    if (
        request.method in _UNSAFE_METHODS
        and (SESSION_COOKIE in request.cookies or request.url.path == LOGIN_PATH)
        and not request.headers.get(CSRF_HEADER)
    ):
        return JSONResponse(
            status_code=403, content={"detail": f"missing {CSRF_HEADER} header"}
        )
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response
