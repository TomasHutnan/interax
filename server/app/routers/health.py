from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.db import get_conn

router = APIRouter(tags=["health"])


@router.get("/health")
def health(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, str]:
    try:
        conn.execute("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
