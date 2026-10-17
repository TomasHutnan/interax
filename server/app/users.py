"""User account operations shared by the manage CLI and the server."""

import re
from typing import Literal, get_args

from psycopg import Connection, errors
from psycopg.rows import DictRow

from app.passwords import hash_password, password_problem

Role = Literal["clinician", "admin"]
ROLES: tuple[Role, ...] = get_args(Role)

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")

# Demo accounts for the dev phase, seeded when SEED_DEV_USERS is on (the default).
# (username, password, role)
DEV_USERS: tuple[tuple[str, str, "Role"], ...] = (
    ("mrnovak", "abcdef123456", "clinician"),
)


class UserError(ValueError):
    """An operation was refused; the message is safe to show to the operator."""


def normalize_username(raw: str) -> str:
    return raw.strip().lower()


def username_problem(username: str) -> str | None:
    if not _USERNAME_RE.fullmatch(username):
        return "username must be 3-64 characters of a-z, 0-9, '.', '_' or '-'"
    return None


def create_user(
    conn: Connection[DictRow], username: str, password: str, role: Role
) -> None:
    username = normalize_username(username)
    if problem := username_problem(username) or password_problem(password):
        raise UserError(problem)
    if role not in ROLES:
        raise UserError(f"role must be one of {', '.join(ROLES)}")
    try:
        with conn.transaction():
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hash_password(password), role),
            )
    except errors.UniqueViolation:
        raise UserError(f"user {username!r} already exists") from None


def set_password(conn: Connection[DictRow], username: str, password: str) -> None:
    """Changes the password and logs the user out everywhere."""
    username = normalize_username(username)
    if problem := password_problem(password):
        raise UserError(problem)
    with conn.transaction():
        row = conn.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s RETURNING id",
            (hash_password(password), username),
        ).fetchone()
        if row is None:
            raise UserError(f"no user {username!r}")
        conn.execute("DELETE FROM sessions WHERE user_id = %s", (row["id"],))


def set_role(conn: Connection[DictRow], username: str, role: Role) -> None:
    username = normalize_username(username)
    if role not in ROLES:
        raise UserError(f"role must be one of {', '.join(ROLES)}")
    with conn.transaction():
        updated = conn.execute(
            "UPDATE users SET role = %s WHERE username = %s", (role, username)
        ).rowcount
    if not updated:
        raise UserError(f"no user {username!r}")


def delete_user(conn: Connection[DictRow], username: str) -> None:
    """Deletes the user; their sessions go with them (ON DELETE CASCADE)."""
    username = normalize_username(username)
    with conn.transaction():
        deleted = conn.execute(
            "DELETE FROM users WHERE username = %s", (username,)
        ).rowcount
    if not deleted:
        raise UserError(f"no user {username!r}")


def list_users(conn: Connection[DictRow]) -> list[DictRow]:
    return conn.execute(
        "SELECT u.username, u.role, u.created_at,"
        " (SELECT count(*) FROM sessions s"
        "   WHERE s.user_id = u.id AND s.expires_at > now()) AS active_sessions"
        " FROM users u ORDER BY u.username"
    ).fetchall()


def ensure_bootstrap_admin(
    conn: Connection[DictRow], username: str, password_hash: str
) -> bool:
    """Creates the admin if there are no users at all; True if it was created."""
    with conn.transaction():
        created = conn.execute(
            "INSERT INTO users (username, password_hash, role)"
            " SELECT %s, %s, 'admin' WHERE NOT EXISTS (SELECT 1 FROM users)",
            (normalize_username(username), password_hash),
        ).rowcount
    return bool(created)


def ensure_user(
    conn: Connection[DictRow], username: str, password_hash: str, role: Role
) -> bool:
    """Creates the user if no user has that name; never touches an existing one.
    True if it was created."""
    with conn.transaction():
        created = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
            " ON CONFLICT (username) DO NOTHING",
            (normalize_username(username), password_hash, role),
        ).rowcount
    return bool(created)
