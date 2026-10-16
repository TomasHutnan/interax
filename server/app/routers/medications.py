from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter(prefix="/medications", tags=["medications"])


class Substance(BaseModel):
    kod_latky: str
    substance_name_en: str | None
    s: str | None
    amnt: str | None
    un: str | None


class MedicationMatch(BaseModel):
    kod_sukl: str
    nazev: str
    sila: str | None
    forma: str | None
    match_score: float
    substances: list[Substance]


@router.get("/substances")
def medication_substances(
    name: Annotated[str, Query(min_length=1)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> MedicationMatch:
    """Best-matching SÚKL product for a free-text name, with its substances' English names."""
    rows = conn.execute(
        "SELECT * FROM match_medication_substances(%s)", (name,)
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="no matching medication")

    first = rows[0]
    return MedicationMatch(
        kod_sukl=first["kod_sukl"],
        nazev=first["nazev"],
        sila=first["sila"],
        forma=first["forma"],
        match_score=first["match_score"],
        substances=[Substance(**row) for row in rows],
    )
