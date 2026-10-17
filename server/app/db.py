from collections.abc import Iterator

from fastapi import Request
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def _check_connection(conn: Connection[DictRow]) -> None:
    """Same as `ConnectionPool.check_connection`, typed for dict-row connections."""
    if conn.autocommit:
        conn.execute("")
        return
    conn.autocommit = True
    try:
        conn.execute("")
    finally:
        conn.autocommit = False


def create_pool() -> ConnectionPool[Connection[DictRow]]:
    # open=False: opened in the app lifespan, so importing this module has no side effects.
    return ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=10,
        connection_class=Connection[DictRow],
        kwargs={
            "row_factory": dict_row,
            # TCP keepalives so idle pooled connections aren't silently dropped by
            # the network in between (Azure Container Apps closes idle TCP flows).
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
        # Ping each connection before handing it out; a dead one (db restarted,
        # connection dropped) is replaced instead of failing the request.
        check=_check_connection,
        max_idle=300,
        open=False,
    )


def get_conn(request: Request) -> Iterator[Connection[DictRow]]:
    with request.app.state.pool.connection() as conn:
        yield conn
