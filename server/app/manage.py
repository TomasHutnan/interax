"""Command-line user management.

    python -m app.manage create-user alice --role clinician
    python -m app.manage set-password alice
    python -m app.manage set-role alice admin
    python -m app.manage delete-user alice
    python -m app.manage list-users
    python -m app.manage migrate

Passwords are prompted for (not echoed), or read from one line of stdin with
--password-stdin. Uses DATABASE_URL like the server, and applies pending
migrations first so it works on a fresh database.
"""

import argparse
import getpass
import sys

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from app.config import settings
from app.migrations import migrate
from app.passwords import MIN_PASSWORD_LENGTH
from app.users import (
    ROLES,
    UserError,
    create_user,
    delete_user,
    list_users,
    set_password,
    set_role,
)


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    password = getpass.getpass(f"Password (min. {MIN_PASSWORD_LENGTH} characters): ")
    if getpass.getpass("Repeat password: ") != password:
        raise UserError("passwords don't match")
    return password


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.manage", description="InteraX user management"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="create a clinician or admin")
    create.add_argument("username")
    create.add_argument("--role", choices=ROLES, required=True)
    create.add_argument("--password-stdin", action="store_true")

    passwd = commands.add_parser(
        "set-password", help="change a password (logs the user out everywhere)"
    )
    passwd.add_argument("username")
    passwd.add_argument("--password-stdin", action="store_true")

    role = commands.add_parser("set-role", help="change a user's role")
    role.add_argument("username")
    role.add_argument("role", choices=ROLES)

    delete = commands.add_parser("delete-user", help="delete a user and their sessions")
    delete.add_argument("username")
    delete.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    commands.add_parser("list-users", help="list users")
    commands.add_parser("migrate", help="only apply pending migrations")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with Connection[DictRow].connect(
            settings.database_url, autocommit=True, row_factory=dict_row
        ) as conn:
            for version in migrate(conn):
                print(f"applied migration {version}")

            match args.command:
                case "create-user":
                    create_user(
                        conn,
                        args.username,
                        _read_password(args.password_stdin),
                        args.role,
                    )
                    print(f"created {args.role} {args.username.strip().lower()!r}")
                case "set-password":
                    set_password(
                        conn, args.username, _read_password(args.password_stdin)
                    )
                    print("password changed; existing sessions were ended")
                case "set-role":
                    set_role(conn, args.username, args.role)
                    print(f"{args.username!r} is now {args.role}")
                case "delete-user":
                    if not args.yes and input(
                        f"Delete user {args.username!r}? [y/N] "
                    ).strip().lower() not in ("y", "yes"):
                        print("aborted")
                        return 1
                    delete_user(conn, args.username)
                    print(f"deleted {args.username!r}")
                case "list-users":
                    users = list_users(conn)
                    if not users:
                        print("no users")
                    for user in users:
                        print(
                            f"{user['username']:<24} {user['role']:<10}"
                            f" created {user['created_at']:%Y-%m-%d %H:%M}"
                            f"  active sessions: {user['active_sessions']}"
                        )
                case "migrate":
                    pass
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except psycopg.OperationalError as exc:
        print(f"error: cannot reach the database: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
