from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter(prefix="/regimens", tags=["regimens"])


class RegimenComponent(BaseModel):
    concept_id: int
    concept_name: str
    concept_code: str


@router.get("/{regimen_id}/components")
def regimen_components(
    regimen_id: int, conn: Annotated[Connection, Depends(get_conn)]
) -> list[RegimenComponent]:
    """Drugs (HemOnc 'Component' concepts) used in a regimen."""
    is_regimen = conn.execute(
        "SELECT 1 FROM concept WHERE concept_id = %s AND concept_class_id = 'Regimen'",
        (regimen_id,),
    ).fetchone()
    if not is_regimen:
        raise HTTPException(status_code=404, detail="regimen not found")

    rows = conn.execute(
        "SELECT * FROM regimen_components(%s)", (regimen_id,)
    ).fetchall()
    return [RegimenComponent(**row) for row in rows]
