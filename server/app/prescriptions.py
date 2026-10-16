"""Prescription lookup against the SÚKL DLP tables (dlp_lecivepripravky/slozeni/latky)."""

from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel

# dlp_slozeni.s: 'L' = active substance; other rows are excipients (amount often "PL").
ACTIVE_SUBSTANCE = "L"

_TO_MG = {"MG": 1.0, "G": 1000.0, "UG": 0.001, "MCG": 0.001}


class Substance(BaseModel):
    name: str
    mg: str


class Prescription(BaseModel):
    drug: str
    subs: list[Substance]
    usage: str = ""


def _format_mg(amnt: str | None, un: str | None) -> str:
    """Amount in mg as a string; units that can't be converted (e.g. IU) keep their unit."""
    if not amnt:
        return ""
    factor = _TO_MG.get((un or "").strip().upper())
    try:
        value = float(amnt.replace(",", "."))
    except ValueError:
        value = None
    if factor is None or value is None:
        return f"{amnt} {un or ''}".strip()
    return f"{value * factor:.6f}".rstrip("0").rstrip(".")


def lookup_prescription(
    conn: Connection[DictRow], name: str, usage: str = ""
) -> Prescription | None:
    """Best-matching SÚKL product for a free-text name, or None if nothing is close enough."""
    rows = conn.execute(
        "SELECT * FROM match_medication_substances(%s)", (name,)
    ).fetchall()
    if not rows:
        return None
    return Prescription(
        drug=rows[0]["nazev"],
        subs=[
            Substance(
                name=row["substance_name_en"] or "",
                mg=_format_mg(row["amnt"], row["un"]),
            )
            for row in rows
            if row["s"] == ACTIVE_SUBSTANCE
        ],
        usage=usage,
    )
