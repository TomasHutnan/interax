"""Dummy login/logout for the demo: two hardcoded accounts, no sessions or tokens."""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

# Uvicorn's logger, so messages show up in the server output without extra logging setup.
log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Demo-only credentials. Replace with real user storage and password hashing before
# this handles anything sensitive.
DUMMY_ACCOUNTS = {
    "doctor": "doctor123",
    "admin": "admin123",
}


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest) -> Response:
    """200 if the credentials match a dummy account, 403 otherwise."""
    expected = DUMMY_ACCOUNTS.get(body.username)
    # compare_digest avoids leaking how much of the password matched via timing.
    if expected is None or not secrets.compare_digest(
        body.password.encode(), expected.encode()
    ):
        raise HTTPException(status_code=403, detail="invalid username or password")
    return Response(status_code=200)


class LogoutResponse(BaseModel):
    detail: str


@router.post("/logout")
def logout() -> LogoutResponse:
    """Dummy logout: there is no session to end, so this always succeeds."""
    log.info("User logged out")
    return LogoutResponse(detail="logged out")
