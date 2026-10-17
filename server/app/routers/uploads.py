import secrets
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Response
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from app.config import settings
from app.db import get_conn
from app.upload_expiry import UploadExpiry, get_upload_expiry

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UploadId = Annotated[str, Path(pattern=r"^\d{6}$", examples=["042137"])]

# Only 1M possible codes, so collisions are realistic once the table fills up; retry.
_MAX_ATTEMPTS = 20


class UploadCreated(BaseModel):
    id: str
    uploaded_at: datetime


class Upload(UploadCreated):
    data: Any


@router.post("", status_code=201)
def create_upload(
    data: Annotated[Any, Body()],
    conn: Annotated[Connection[DictRow], Depends(get_conn)],
    expiry: Annotated[UploadExpiry, Depends(get_upload_expiry)],
) -> UploadCreated:
    """Store any JSON body under a new random 6-digit code, deleted after UPLOAD_TTL."""
    for _ in range(_MAX_ATTEMPTS):
        code = f"{secrets.randbelow(1_000_000):06d}"
        row = conn.execute(
            "INSERT INTO uploads (id, data) VALUES (%s, %s)"
            " ON CONFLICT (id) DO NOTHING RETURNING id, uploaded_at",
            (code, Jsonb(data)),
        ).fetchone()
        if row is not None:
            # Commit now rather than when the dependency closes, so a GET right after sees it.
            conn.commit()
            expiry.schedule(row["id"], row["uploaded_at"])
            return UploadCreated(**row)
    raise HTTPException(status_code=503, detail="could not allocate a free code")


@router.get("/{upload_id}")
def get_upload(
    upload_id: UploadId, conn: Annotated[Connection[DictRow], Depends(get_conn)]
) -> Upload:
    row = conn.execute(
        "SELECT id, data, uploaded_at FROM uploads"
        " WHERE id = %s AND uploaded_at > now() - %s",
        (upload_id, settings.upload_ttl),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="upload not found")
    return Upload(**row)


@router.delete("/{upload_id}", status_code=204)
def delete_upload(
    upload_id: UploadId, conn: Annotated[Connection[DictRow], Depends(get_conn)]
) -> Response:
    deleted = conn.execute("DELETE FROM uploads WHERE id = %s", (upload_id,)).rowcount
    conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="upload not found")
    return Response(status_code=200)
