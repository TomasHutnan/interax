"""InterSystems IRIS Clinical RAG, APIM Adjudication & FHIR R4 Pipeline."""

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import iris
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from rapidfuzz import fuzz, process
from requests.auth import HTTPBasicAuth
from sentence_transformers import SentenceTransformer

log = logging.getLogger("uvicorn.error")

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if not ROOT_ENV_FILE.exists():
    ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)
load_dotenv(override=False)

IRIS_HOST = os.getenv("IRIS_HOST", "")
IRIS_PORT = int(os.getenv("IRIS_PORT", "1972"))
IRIS_HTTP_PORT = int(os.getenv("IRIS_HTTP_PORT", "52773"))
IRIS_NAMESPACE = os.getenv("IRIS_NAMESPACE", "USER")
IRIS_USER = os.getenv("IRIS_USER", "_SYSTEM")
IRIS_PASSWORD = os.getenv("IRIS_PASSWORD", "")

APIM_BASE_URL = os.getenv("UNSLOTH_BASE_URL", "").rstrip("/")
APIM_API_KEY = os.getenv("UNSLOTH_API_KEY", "")
APIM_MODEL = os.getenv("UNSLOTH_MODEL", "gpt-6-1-sol-dz-eu")

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SYSTEM_PROMPT = (
    "You are a deterministic clinical pharmacology analyzer. "
    "Analyze the provided normalized medications, deterministic interaction records, and retrieved pharmacogenomic guideline chunks, using established clinical pharmacology when mechanism_text only states the risk level. "
    "Do not perform conversational synthesis, do not provide actionable suggestions, and do not include mitigation planning or clinical advice. "
    'Produce one output object per interaction pairing found in ddinter_interactions, keyed by "SubstanceA + SubstanceB". '
    'Each interaction pairing object MUST contain ONLY two fields: "pathophysiological_mechanism" and "clinical_consequence". '
    "Each field value MUST be at most 10 concise words (<= 10 words). "
    'Whenever an interaction has no known mechanism or consequence (e.g., risk_level is "Unknown" with no known mechanism), output an empty string "" instead of stating "unknown", "unknown mechanism", "unspecified", or similar placeholder text. '
    "Output ONLY valid JSON in this exact shape:\n"
    "{\n"
    '  "SubstanceA + SubstanceB": {\n'
    '    "pathophysiological_mechanism": "<max 10 concise words, or empty string>",\n'
    '    "clinical_consequence": "<max 10 concise words, or empty string>"\n'
    "  }\n"
    "}"
)





@dataclass
class RagInteraction:
    substance_1: str
    substance_2: str
    pathophysiological_mechanism: str
    clinical_consequence: str
    severity: str


@dataclass
class _ResolvedMed:
    input_text: str
    sukl_code: str
    brand_name: str
    active_substance: str
    canonical_name: str
    strength: str
    atc_code: str
    atc_name: str


class _AdjudicatedPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pathophysiological_mechanism: str
    clinical_consequence: str


_embedder: SentenceTransformer | None = None
_sukl_cache: list[tuple] | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def _get_conn():
    return iris.connect(
        f"{IRIS_HOST}:{IRIS_PORT}/{IRIS_NAMESPACE}", IRIS_USER, IRIS_PASSWORD
    )


def _canonical_substance(active_substance: str, atc_name: str) -> str:
    if atc_name and len(atc_name.split()) == 1:
        return atc_name.strip().title()
    if active_substance:
        cleaned = re.sub(
            r"\b(citrate|hydrochloride|hemihydrate|sodium|potassium|mesilate|mesylate|maleate|tartrate|sulfate|sulphate|acetate|calcium|dihydrate|monohydrate|anhydrous|fumarate|succinate|phosphate|besilate|besylate|bromide|chloride|clathrate)\b",
            "",
            active_substance,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;-/")
        if cleaned:
            return cleaned.title()
    return active_substance.split()[0].title() if active_substance else ""


def _resolve_medications(conn, inputs: list[str]) -> list[_ResolvedMed]:
    global _sukl_cache
    resolved: list[_ResolvedMed] = []
    cur = conn.cursor()

    for raw in inputs:
        q = raw.strip()
        row = None
        if re.fullmatch(r"\d{7}", q):
            cur.execute(
                "SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName FROM ClinicalData.SuklRegistry WHERE SuklCode = ?",
                [q],
            )
            r = cur.fetchone()
            row = tuple(r) if r is not None else None

        if not row or not row[2]:
            token = re.split(r"[\s,;/()+-]+", q)[0].strip()
            cur.execute(
                """
                SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName
                FROM ClinicalData.SuklRegistry
                WHERE (LOWER(BrandName) %STARTSWITH LOWER(?) OR LOWER(ActiveSubstance) = LOWER(?) OR LOWER(SubstanceCzech) = LOWER(?))
                  AND ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
                ORDER BY LENGTH(BrandName) ASC
                """,
                [q, token, token],
            )
            r = cur.fetchone()
            row = tuple(r) if r is not None else None

            if not row or not row[2]:
                cur.execute(
                    """
                    SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName
                    FROM ClinicalData.SuklRegistry
                    WHERE (LOWER(BrandName) %STARTSWITH LOWER(?) OR LOWER(ActiveSubstance) %STARTSWITH LOWER(?))
                      AND ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
                    ORDER BY LENGTH(BrandName) ASC
                    """,
                    [token, token],
                )
                r = cur.fetchone()
                row = tuple(r) if r is not None else None

        if not row or not row[2]:
            if _sukl_cache is None:
                cur.execute(
                    "SELECT SuklCode, BrandName, ActiveSubstance, Strength, AtcCode, AtcName FROM ClinicalData.SuklRegistry WHERE ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''"
                )
                _sukl_cache = [tuple(x) for x in cur.fetchall()]
            choices = [f"{r[1]} {r[3]} ({r[2]})" for r in _sukl_cache]
            best = process.extractOne(q, choices, scorer=fuzz.WRatio)
            if best and best[1] >= 60:
                row = _sukl_cache[best[2]]

        if row and row[2]:
            sukl, brand, act_sub, strength, atc_code, atc_name = row
            canon = _canonical_substance(act_sub, atc_name)
            resolved.append(
                _ResolvedMed(raw, sukl, brand, act_sub, canon, strength, atc_code, atc_name)
            )
        else:
            token = re.split(r"[\s,;/()+-]+", q)[0].strip().title()
            resolved.append(_ResolvedMed(raw, "0000000", q, token, token, "", "", ""))

    cur.close()
    return resolved


_UNKNOWN_RE = re.compile(
    r"^(unknown|not\s+available|unavailable|not\s+specified|unspecified|no\s+available\s+info\w*|no\s+information\b.*|n/?a|none)\b",
    re.IGNORECASE,
)


def _enforce_max_words(text: str, max_words: int = 10) -> str:
    cleaned = text.strip()
    if not cleaned or _UNKNOWN_RE.match(cleaned) or "unknown" in cleaned.lower():
        return ""
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
    return " ".join(words[:max_words]).rstrip(".,;:") + "."



_FHIR_SEVERITY_MAP = {
    "major": "high",
    "high": "high",
    "critical": "high",
    "contraindicated": "high",
    "moderate": "moderate",
    "medium": "moderate",
    "minor": "low",
    "low": "low",
}


def _match_med_ref(substance: str, sub_to_ref: dict[str, str]) -> str | None:
    s_norm = substance.strip().lower()
    if not s_norm:
        return None
    if s_norm in sub_to_ref:
        return sub_to_ref[s_norm]
    for key, ref in sub_to_ref.items():
        if key and (s_norm in key or key in s_norm):
            return ref
    return None


def upload_to_fhir(
    meds: list[dict[str, object]],
    interactions: list[tuple[str, str, str, str]],
) -> dict[str, object]:
    """Upload prescriptions (MedicationStatement) and interactions (DetectedIssue) to IRIS FHIR R4."""
    session_uuid = str(uuid.uuid4())
    subject_ref = f"Patient/{session_uuid}"
    base_url = f"http://{IRIS_HOST}:{IRIS_HTTP_PORT}/csp/healthshare/fhir/r4"
    auth = HTTPBasicAuth(IRIS_USER, IRIS_PASSWORD)
    headers = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
        "Prefer": "return=representation",
    }

    conn = _get_conn()
    try:
        queries = []
        for m in meds:
            drug = str(m.get("drug") or "").strip()
            subs = [str(s).strip() for s in (m.get("subs") or []) if str(s).strip()]
            queries.append(drug or (subs[0] if subs else "Unknown"))
        resolved_list = _resolve_medications(conn, queries) if queries else []
    finally:
        conn.close()

    sub_to_ref: dict[str, str] = {}
    created_meds: list[dict[str, object]] = []

    for m, resolved in zip(meds, resolved_list):
        drug = str(m.get("drug") or resolved.brand_name).strip()
        mg = str(m.get("mg") or "").strip()
        subs = [str(s).strip() for s in (m.get("subs") or []) if str(s).strip()]
        usage = str(m.get("usage") or "").strip()

        coding = [
            {
                "system": "https://sukl.cz/terminology/CodeSystem/dlp",
                "code": resolved.sukl_code,
                "display": f"{resolved.brand_name} {resolved.strength}".strip() or drug,
            }
        ]
        if resolved.atc_code:
            coding.append(
                {
                    "system": "http://www.whocc.no/atc",
                    "code": resolved.atc_code,
                    "display": resolved.atc_name or resolved.canonical_name,
                }
            )

        subs_label = ", ".join(subs) if subs else resolved.active_substance
        ms_payload: dict[str, object] = {
            "resourceType": "MedicationStatement",
            "status": "active",
            "medicationCodeableConcept": {
                "coding": coding,
                "text": f"{drug} ({subs_label})" if subs_label else drug,
            },
            "subject": {"reference": subject_ref},
        }
        dosage_parts = [p for p in [f"{mg} mg" if mg and mg.replace(".", "").replace("/", "").isdigit() else mg, usage] if p]
        if dosage_parts:
            ms_payload["dosage"] = [{"text": " | ".join(dosage_parts)}]

        r = requests.post(
            f"{base_url}/MedicationStatement",
            auth=auth,
            headers=headers,
            json=ms_payload,
            timeout=10,
        )
        r.raise_for_status()
        ms_id = str(r.json().get("id", "unknown"))
        ref = f"MedicationStatement/{ms_id}"

        for key in [drug, resolved.canonical_name, resolved.active_substance, *subs]:
            if key and key.strip():
                sub_to_ref[key.strip().lower()] = ref

        created_meds.append(
            {
                "id": ms_id,
                "reference": ref,
                "drug": drug,
                "sukl_code": resolved.sukl_code,
                "status_code": r.status_code,
            }
        )

    created_issues: list[dict[str, object]] = []
    for sub1, sub2, description, severity in interactions:
        fhir_severity = _FHIR_SEVERITY_MAP.get(str(severity).strip().lower(), "high")
        implicated = []
        for s in (sub1, sub2):
            matched_ref = _match_med_ref(s, sub_to_ref)
            if matched_ref:
                implicated.append({"reference": matched_ref, "display": s})

        di_payload: dict[str, object] = {
            "resourceType": "DetectedIssue",
            "status": "final",
            "severity": fhir_severity,
            "code": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "DRG",
                        "display": "Drug Interaction Alert",
                    }
                ]
            },
            "subject": {"reference": subject_ref},
            "implicated": implicated,
            "detail": f"[{sub1} + {sub2}] ({severity}) {description}".strip(),
        }
        r_di = requests.post(
            f"{base_url}/DetectedIssue",
            auth=auth,
            headers=headers,
            json=di_payload,
            timeout=10,
        )
        if r_di.status_code == 400 and "UnexpectedPropertyName" in r_di.text:
            r4_payload = {k: v for k, v in di_payload.items() if k != "subject"}
            r4_payload["patient"] = di_payload["subject"]
            r_di = requests.post(
                f"{base_url}/DetectedIssue",
                auth=auth,
                headers=headers,
                json=r4_payload,
                timeout=10,
            )
        r_di.raise_for_status()
        di_id = str(r_di.json().get("id", "unknown"))
        created_issues.append(
            {
                "id": di_id,
                "reference": f"DetectedIssue/{di_id}",
                "substances": [sub1, sub2],
                "severity": fhir_severity,
                "status_code": r_di.status_code,
            }
        )

    return {
        "session_uuid": session_uuid,
        "subject_reference": subject_ref,
        "medication_statements": created_meds,
        "detected_issues": created_issues,
    }


def check_rag_interactions(substances: list[str]) -> list[RagInteraction]:
    """Run the 5-step IRIS SQL + Vector RAG + APIM LLM + FHIR R4 pipeline."""
    if len(substances) < 2:
        return []

    conn = _get_conn()
    try:
        # 1. Normalize inputs to SÚKL / INN / WHO ATC
        resolved = _resolve_medications(conn, substances)
        canon_to_input = {m.canonical_name.lower(): m.input_text for m in resolved}
        unique_canons = sorted({m.canonical_name for m in resolved if m.canonical_name})
        if len(unique_canons) < 2:
            return []

        # 2. Query all DDInter severity rows from ClinicalData.Interactions
        cur = conn.cursor()
        ddi_hits: list[dict[str, str]] = []
        for i in range(len(unique_canons)):
            for j in range(i + 1, len(unique_canons)):
                sub_a, sub_b = unique_canons[i], unique_canons[j]
                cur.execute(
                    """
                    SELECT SubstanceA, SubstanceB, RiskLevel, MechanismText
                    FROM ClinicalData.Interactions
                    WHERE (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                       OR (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                    """,
                    [sub_a, sub_b, sub_b, sub_a],
                )
                for r in [tuple(row) for row in cur.fetchall()]:
                    ddi_hits.append(
                        {
                            "pairing": f"{r[0]} + {r[1]}",
                            "substance_a": r[0],
                            "substance_b": r[1],
                            "risk_level": r[2],
                            "mechanism_text": r[3],
                        }
                    )

        if not ddi_hits:
            cur.close()
            return []

        # 3. Native IRIS VECTOR_DOT_PRODUCT retrieval (Top 2 if <=3 substances, Top 1 if >3)
        per_sub_k = 1 if len(unique_canons) > 3 else 2
        mech_context = "; ".join(d["mechanism_text"] for d in ddi_hits)
        query_text = (
            f"Pharmacogenomic pathway, enzyme inhibition, and drug interaction mechanism for "
            f"{', '.join(unique_canons)}. {mech_context}"
        )
        emb = _get_embedder().encode([query_text], normalize_embeddings=True)[0]
        vec_str = ",".join(f"{float(x):.6f}" for x in emb)

        cpic_chunks: list[dict[str, object]] = []
        for sub in unique_canons:
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
            for r in [tuple(row) for row in cur.fetchall()]:
                cpic_chunks.append(
                    {
                        "substance": r[0],
                        "source": r[1],
                        "score": round(float(r[3]), 4),
                        "content": r[2],
                    }
                )
        cur.close()
    finally:
        conn.close()

    # 4. Context-Aware LLM Adjudication via Azure APIM (one 2-field <=10-word object per pairing)
    user_payload = json.dumps(
        {
            "required_pairings": [d["pairing"] for d in ddi_hits],
            "medications": [
                {
                    "sukl_code": m.sukl_code,
                    "brand_name": m.brand_name,
                    "active_substance": m.canonical_name,
                    "atc_code": m.atc_code,
                }
                for m in resolved
            ],
            "ddinter_interactions": ddi_hits,
            "cpic_guideline_chunks": cpic_chunks,
        },
        ensure_ascii=False,
    )

    resp = requests.post(
        f"{APIM_BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "api-key": APIM_API_KEY},
        json={
            "model": APIM_MODEL,
            "stream": False,
            "temperature": 1,
            "max_completion_tokens": 1200,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    parsed = json.loads(cleaned[start : end + 1])

    adjudications: dict[str, _AdjudicatedPair] = {}
    for pair_key, val in parsed.items():
        if isinstance(val, dict) and "pathophysiological_mechanism" in val and "clinical_consequence" in val:
            adjudications[pair_key] = _AdjudicatedPair(
                pathophysiological_mechanism=_enforce_max_words(
                    str(val["pathophysiological_mechanism"]), 10
                ),
                clinical_consequence=_enforce_max_words(
                    str(val["clinical_consequence"]), 10
                ),
            )

    # Map back to RagInteraction objects with both fields preserved
    results: list[RagInteraction] = []
    for d in ddi_hits:
        pair_key = d["pairing"]
        rev_key = f"{d['substance_b']} + {d['substance_a']}"
        adj = adjudications.get(pair_key) or adjudications.get(rev_key)
        mech = (
            adj.pathophysiological_mechanism
            if adj is not None
            else _enforce_max_words(d["mechanism_text"], 10)
        )
        conseq = adj.clinical_consequence if adj is not None else ""


        in_1 = canon_to_input.get(d["substance_a"].lower(), d["substance_a"])
        in_2 = canon_to_input.get(d["substance_b"].lower(), d["substance_b"])
        results.append(
            RagInteraction(
                substance_1=in_1,
                substance_2=in_2,
                pathophysiological_mechanism=mech,
                clinical_consequence=conseq,
                severity=d["risk_level"].lower(),
            )
        )

    return results
