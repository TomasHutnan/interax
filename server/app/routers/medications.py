from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.rows import DictRow

from app.auth import require_user
from app.db import get_conn
from app.prescriptions import Prescription, lookup_prescription

router = APIRouter(
    prefix="/api/medications",
    tags=["medications"],
    dependencies=[Depends(require_user)],
)


@router.get("/substances")
def medication_substances(
    name: Annotated[str, Query(min_length=1)],
    conn: Annotated[Connection[DictRow], Depends(get_conn)],
) -> Prescription:
    """Best-matching SÚKL product for a free-text name, with its active substances."""
    prescription = lookup_prescription(conn, name)
    if prescription is None:
        raise HTTPException(status_code=404, detail="no matching medication")
    return prescription
