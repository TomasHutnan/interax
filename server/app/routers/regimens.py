from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter(prefix="/regimens", tags=["regimens"])


class RegimenComponent(BaseModel):
    concept_name: str


@router.get("/components")
def regimen_components(
    name: Annotated[str, Query(min_length=1)],
    conn: Annotated[Connection[DictRow], Depends(get_conn)],
) -> list[RegimenComponent]:
    """Drugs (HemOnc 'Component' concepts) used in a regimen, looked up by name.

    Matching is case-insensitive and exact. The name is a query parameter because
    regimen names can contain '/' (e.g. "FOLFOX 7/sLV5FU2").
    """
    matches = len(
        conn.execute(
            """
            SELECT concept_id
            FROM concept
            WHERE lower(concept_name) = lower(btrim(%s))
              AND domain_id = 'Regimen'
              AND concept_class_id = 'Regimen'
              AND invalid_reason IS NULL
            """,
            (name,),
        ).fetchall()
    )
    if matches == 0:
        raise HTTPException(status_code=404, detail="regimen not found")
    if matches > 1:
        raise HTTPException(
            status_code=409, detail=f"regimen name is ambiguous ({matches} matches)"
        )

    rows = conn.execute("SELECT * FROM regimen_components(%s)", (name,)).fetchall()
    return [RegimenComponent(**row) for row in rows]
