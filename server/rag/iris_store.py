"""InterSystems IRIS SQL normalization, DDInter lookup, and CPIC vector retrieval."""

import re

from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer

from rag.config import EMBEDDING_MODEL_NAME, ResolvedMed

_SALT_RE = re.compile(
    r"\b(citrate|hydrochloride|hemihydrate|sodium|potassium|mesilate|mesylate|"
    r"maleate|tartrate|sulfate|sulphate|acetate|calcium|dihydrate|monohydrate|"
    r"anhydrous|fumarate|succinate|phosphate|besilate|besylate|bromide|chloride|clathrate)\b",
    re.IGNORECASE,
)

_embedder: SentenceTransformer | None = None
_sukl_cache: list[tuple] | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def _canonical_substance(active_substance: str, atc_name: str) -> str:
    if atc_name and len(atc_name.split()) == 1:
        return atc_name.strip().title()
    if not active_substance:
        return ""
    cleaned = _SALT_RE.sub("", active_substance).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;-/")
    if cleaned:
        return cleaned.title()
    return active_substance.split()[0].title()


def _fetch_one_tuple(cur, sql: str, params: list[str]) -> tuple | None:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    materialized = tuple(row)
    return materialized if materialized[2] else None


def _fuzzy_match_sukl(cur, query: str) -> tuple | None:
    global _sukl_cache
    if _sukl_cache is None:
        cur.execute(
            "SELECT SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName "
            "FROM ClinicalData.SuklRegistry "
            "WHERE ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''"
        )
        _sukl_cache = [tuple(x) for x in cur.fetchall()]

    choices = [f"{r[1]} {r[3]} ({r[2]})" for r in _sukl_cache]
    best = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if best and best[1] >= 60:
        return _sukl_cache[best[2]]
    return None


def _resolve_single_medication(cur, raw: str) -> ResolvedMed:
    query = raw.strip()
    token = re.split(r"[\s,;/()+-]+", query)[0].strip()

    row = None
    if re.fullmatch(r"\d{7}", query):
        row = _fetch_one_tuple(
            cur,
            "SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName "
            "FROM ClinicalData.SuklRegistry WHERE SuklCode = ?",
            [query],
        )

    if not row:
        row = _fetch_one_tuple(
            cur,
            """
            SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName
            FROM ClinicalData.SuklRegistry
            WHERE (LOWER(BrandName) %STARTSWITH LOWER(?) OR LOWER(ActiveSubstance) = LOWER(?) OR LOWER(SubstanceCzech) = LOWER(?))
              AND ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
            ORDER BY LENGTH(BrandName) ASC
            """,
            [query, token, token],
        )

    if not row:
        row = _fetch_one_tuple(
            cur,
            """
            SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName
            FROM ClinicalData.SuklRegistry
            WHERE (LOWER(BrandName) %STARTSWITH LOWER(?) OR LOWER(ActiveSubstance) %STARTSWITH LOWER(?))
              AND ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
            ORDER BY LENGTH(BrandName) ASC
            """,
            [token, token],
        )

    if not row:
        row = _fuzzy_match_sukl(cur, query)

    if not row:
        fallback = token.title()
        return ResolvedMed(raw, "0000000", query, fallback, fallback, "", "", "")

    sukl, brand, act_sub, strength, atc_code, atc_name = row
    canon = _canonical_substance(act_sub, atc_name)
    return ResolvedMed(raw, sukl, brand, act_sub, canon, strength, atc_code, atc_name)


def resolve_medications(conn, inputs: list[str]) -> list[ResolvedMed]:
    """Normalize raw drug/substance strings against ClinicalData.SuklRegistry."""
    cur = conn.cursor()
    try:
        return [_resolve_single_medication(cur, raw) for raw in inputs]
    finally:
        cur.close()


def query_ddinter_interactions(cur, canonical_substances: list[str]) -> list[dict[str, str]]:
    """Query all DDInter interaction rows for every pair of canonical substances."""
    hits: list[dict[str, str]] = []
    for i, sub_a in enumerate(canonical_substances):
        for sub_b in canonical_substances[i + 1 :]:
            cur.execute(
                """
                SELECT SubstanceA, SubstanceB, RiskLevel, MechanismText
                FROM ClinicalData.Interactions
                WHERE (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                   OR (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                """,
                [sub_a, sub_b, sub_b, sub_a],
            )
            for row in [tuple(r) for r in cur.fetchall()]:
                hits.append(
                    {
                        "pairing": f"{row[0]} + {row[1]}",
                        "substance_a": row[0],
                        "substance_b": row[1],
                        "risk_level": row[2],
                        "mechanism_text": row[3],
                    }
                )
    return hits


def retrieve_cpic_chunks(
    cur,
    canonical_substances: list[str],
    ddi_hits: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Retrieve top CPIC guideline chunks per substance using IRIS VECTOR_DOT_PRODUCT."""
    per_sub_k = 1 if len(canonical_substances) > 3 else 2
    mech_context = "; ".join(d["mechanism_text"] for d in ddi_hits)
    query_text = (
        f"Pharmacogenomic pathway, enzyme inhibition, and drug interaction mechanism for "
        f"{', '.join(canonical_substances)}. {mech_context}"
    )
    emb = _get_embedder().encode([query_text], normalize_embeddings=True)[0]
    vec_str = ",".join(f"{float(x):.6f}" for x in emb)

    chunks: list[dict[str, object]] = []
    for sub in canonical_substances:
        cur.execute(
            f"""
            SELECT TOP {per_sub_k} SubstanceName, SourceFile, ChunkContent,
                   VECTOR_DOT_PRODUCT(Embedding, TO_VECTOR(?, DOUBLE, 384)) AS Score
            FROM ClinicalKnowledge.CpicVectors
            WHERE LOWER(SubstanceName) = LOWER(?)
            ORDER BY Score DESC
            """,
            [vec_str, sub],
        )
        for row in [tuple(r) for r in cur.fetchall()]:
            chunks.append(
                {
                    "substance": row[0],
                    "source": row[1],
                    "score": round(float(row[3]), 4),
                    "content": row[2],
                }
            )
    return chunks
