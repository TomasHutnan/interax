"""Prescription lookup against the SÚKL DLP tables (dlp_lecivepripravky/slozeni/latky)."""

from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel

# dlp_slozeni.s: 'L' = active substance; other rows are excipients (amount often "PL").
ACTIVE_SUBSTANCE = "L"

_TO_MG = {"MG": 1.0, "G": 1000.0, "UG": 0.001, "MCG": 0.001}


class Prescription(BaseModel):
    drug: str
    # Per active substance in `subs` order, e.g. "50 mg", "450/50 mg"; parts that
    # can't be converted keep their own unit: "450 mg/1000 IU".
    mg: str = ""
    subs: list[str] = []
    usage: str = ""


def _amount_in_mg(amnt: str | None, un: str | None) -> str | None:
    """Numeric amount converted to mg, or None if it can't be converted (e.g. IU)."""
    factor = _TO_MG.get((un or "").strip().upper())
    if not amnt or factor is None:
        return None
    try:
        value = float(amnt.replace(",", "."))
    except ValueError:
        return None
    return f"{value * factor:.6f}".rstrip("0").rstrip(".")


def _format_mg(rows: list[DictRow]) -> str:
    amounts = [_amount_in_mg(row["amnt"], row["un"]) for row in rows]
    converted = [mg for mg in amounts if mg is not None]
    if converted and len(converted) == len(amounts):
        return "/".join(converted) + " mg"
    return "/".join(
        f"{mg} mg"
        if mg is not None
        else f"{row['amnt'] or ''} {row['un'] or ''}".strip()
        for mg, row in zip(amounts, rows)
    )


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

    Existing medications get their usage updated (only when the scan read one) and
    their strength refreshed from SÚKL (only when the scan matched the drug there);
    new ones are appended. The order of the current list is preserved.
    """
    merged = [med.model_copy(deep=True) for med in meds]
    for new in scanned:
        existing = next((med for med in merged if _same_medication(med, new)), None)
        if existing is None:
            merged.append(new)
            continue
        if new.usage:
            existing.usage = new.usage
        if new.mg:
            # `mg` is positional per substance, so `subs` must come along with it.
            existing.mg = new.mg
            existing.subs = new.subs
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
        mg=_format_mg(active),
        subs=[row["substance_name_en"] or "" for row in active],
        usage=usage,
    )
