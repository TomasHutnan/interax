"""Clinician login, logout and session lookup."""

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    SESSION_COOKIE,
    Throttle,
    User,
    clear_session_cookie,
    create_session,
    delete_expired_sessions,
    delete_session,
    require_user,
    retry_after_header,
    set_session_cookie,
)
from app.passwords import (
    MAX_PASSWORD_LENGTH,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.users import Role, normalize_username

# Uvicorn's logger, so messages show up in the server output without extra logging setup.
log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Slows down guessing one account's password, and one client guessing many.
_user_throttle = Throttle(max_failures=10, window=timedelta(minutes=15))
_ip_throttle = Throttle(max_failures=50, window=timedelta(minutes=15))

_INVALID = "invalid username or password"


class LoginRequest(BaseModel):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]


class Me(BaseModel):
    username: str
    role: Role


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> Me:
    """Starts a session (cookie) for valid credentials.

    401 with a generic message for any wrong username/password, 429 (with
    Retry-After) after too many failures for the account or the client.
    """
    username = normalize_username(body.username)
    client = request.client.host if request.client else "unknown"

    wait = max(_user_throttle.retry_after(username), _ip_throttle.retry_after(client))
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail="too many failed logins, try again later",
            headers=retry_after_header(wait),
        )

    with request.app.state.pool.connection() as conn:
        row = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = %s",
            (username,),
        ).fetchone()
        if not verify_password(row["password_hash"] if row else None, body.password):
            _user_throttle.fail(username)
            _ip_throttle.fail(client)
            log.info("failed login for %r from %s", username, client)
            raise HTTPException(status_code=401, detail=_INVALID)
        assert row is not None

        if needs_rehash(row["password_hash"]):
            conn.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(body.password), row["id"]),
            )
        delete_expired_sessions(conn)
        # Always a fresh token, so a session id planted before login is useless.
        token = create_session(conn, row["id"])

    _user_throttle.reset(username)
    set_session_cookie(response, token)
    log.info("login %r from %s", row["username"], client)
    return Me(username=row["username"], role=row["role"])


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    """Ends the current session server-side and clears the cookie. Always 204."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with request.app.state.pool.connection() as conn:
            delete_session(conn, token)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/me")
def me(user: Annotated[User, Depends(require_user)]) -> Me:
    """The logged-in user; 401 if there is no valid session."""
    return Me(username=user.username, role=user.role)
