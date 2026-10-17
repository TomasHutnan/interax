"""Settings, sourced from the repo-root .env (shared with the db service).

Locally the file is loaded from the repository root; in Docker it doesn't exist
and compose injects the same variables via `env_file`. Variables already set in
the process environment always win, and python-dotenv expands ${VAR} references
using them too, so e.g. `POSTGRES_HOST=localhost` changes DATABASE_URL.
"""

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    upload_ttl: timedelta
    session_ttl: timedelta
    session_idle_ttl: timedelta
    session_cookie_secure: bool
    bootstrap_admin_username: str | None
    bootstrap_admin_password: str | None


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set (expected in {ROOT_ENV_FILE} or the environment)"
        )
    return value


def _positive_seconds(name: str, default: int) -> timedelta:
    raw = os.getenv(name)
    if not raw:
        return timedelta(seconds=default)
    try:
        seconds = int(raw)
    except ValueError:
        raise RuntimeError(
            f"{name} must be a whole number of seconds, got {raw!r}"
        ) from None
    if seconds <= 0:
        raise RuntimeError(f"{name} must be positive, got {seconds}")
    return timedelta(seconds=seconds)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if not raw:
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise RuntimeError(f"{name} must be true or false, got {raw!r}")


settings = Settings(
    database_url=_require("DATABASE_URL"),
    # Seconds an upload lives before it's deleted.
    upload_ttl=_positive_seconds("UPLOAD_TTL", 3600),
    # Clinician sessions end this long after login, however active they are...
    session_ttl=_positive_seconds("SESSION_TTL", 12 * 3600),
    # ...or after this long without a request.
    session_idle_ttl=_positive_seconds("SESSION_IDLE_TTL", 3600),
    # Only turn off for local development over plain http (Safari drops Secure
    # cookies on http://localhost; Chrome and Firefox accept them).
    session_cookie_secure=_bool("SESSION_COOKIE_SECURE", True),
    # Optional: creates this admin whenever the users table is empty, e.g. after
    # the (volume-less) Azure database restarted. Both must be set to take effect.
    bootstrap_admin_username=os.getenv("BOOTSTRAP_ADMIN_USERNAME") or None,
    bootstrap_admin_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or None,
)
