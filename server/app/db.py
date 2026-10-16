from collections.abc import Iterator

from fastapi import Request
from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def create_pool() -> ConnectionPool[Connection[DictRow]]:
    # open=False: opened in the app lifespan, so importing this module has no side effects.
    return ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=10,
        connection_class=Connection[DictRow],
        kwargs={"row_factory": dict_row},
        open=False,
    )


def get_conn(request: Request) -> Iterator[Connection[DictRow]]:
    with request.app.state.pool.connection() as conn:
        yield conn
