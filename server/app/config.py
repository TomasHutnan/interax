"""Settings, sourced from the repo-root .env (shared with the db service).

Locally the file is loaded from the repository root; in Docker it doesn't exist
and compose injects the same variables via `env_file`. Variables already set in
the process environment always win, and python-dotenv expands ${VAR} references
using them too, so e.g. `POSTGRES_HOST=localhost` changes DATABASE_URL.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: list[str]


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set (expected in {ROOT_ENV_FILE} or the environment)"
        )
    return value


settings = Settings(
    database_url=_require("DATABASE_URL"),
    cors_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
)
