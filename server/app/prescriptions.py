"""Prescription lookup against the SÚKL DLP tables (dlp_lecivepripravky/slozeni/latky)."""

from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel

# dlp_slozeni.s: 'L' = active substance; other rows are excipients (amount often "PL").
ACTIVE_SUBSTANCE = "L"

_TO_MG = {"MG": 1.0, "G": 1000.0, "UG": 0.001, "MCG": 0.001}


class Prescription(BaseModel):
    drug: str
    mg: str = ""  # per active substance, "/"-joined in `subs` order (e.g. "450/50")
    subs: list[str] = []
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


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _same_medication(a: Prescription, b: Prescription) -> bool:
    # Name only: matching on substances would merge different products (e.g. a
    # generic) and silently apply one product's usage to another.
    return _normalize(a.drug) == _normalize(b.drug)


def merge_prescriptions(
    meds: list[Prescription], scanned: list[Prescription]
) -> list[Prescription]:
    """Apply scanned prescriptions to the current list.

    Existing medications only get their usage updated (and only when the scan read
    one); new ones are appended. The order of the current list is preserved.
    """
    merged = [med.model_copy(deep=True) for med in meds]
    for new in scanned:
        existing = next((med for med in merged if _same_medication(med, new)), None)
        if existing is None:
            merged.append(new)
        elif new.usage:
            existing.usage = new.usage
    return merged


def lookup_prescription(
    conn: Connection[DictRow], name: str, usage: str = ""
) -> Prescription | None:
    """Best-matching SÚKL product for a free-text name, or None if nothing is close enough."""
    rows = conn.execute(
        "SELECT * FROM match_medication_substances(%s)", (name,)
    ).fetchall()
    if not rows:
        return None
    active = [row for row in rows if row["s"] == ACTIVE_SUBSTANCE]
    return Prescription(
        drug=rows[0]["nazev"],
        mg="/".join(_format_mg(row["amnt"], row["un"]) for row in active),
        subs=[row["substance_name_en"] or "" for row in active],
        usage=usage,
    )
