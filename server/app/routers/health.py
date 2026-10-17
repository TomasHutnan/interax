from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg import Connection

from app.db import get_conn

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    request: Request, conn: Annotated[Connection, Depends(get_conn)]
) -> dict[str, str]:
    """200 once the database is reachable and its schema is migrated, 503 before."""
    try:
        conn.execute("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    if not request.app.state.schema.ready.is_set():
        raise HTTPException(status_code=503, detail="database schema not ready")
    return {"status": "ok"}
