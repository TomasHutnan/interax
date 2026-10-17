"""Phase 3 & 4: IRIS Retrieval, APIM LLM Adjudication, and FHIR R4 Persistence Pipeline."""

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import iris
import requests
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process
from requests.auth import HTTPBasicAuth
from sentence_transformers import SentenceTransformer

import config


@dataclass
class ResolvedMedication:
    input_text: str
    sukl_code: str
    brand_name: str
    active_substance: str
    substance_czech: str
    strength: str
    form: str
    atc_code: str
    atc_name: str
    match_method: str


@dataclass
class DeterministicDDI:
    substance_a: str
    substance_b: str
    risk_level: str
    mechanism_text: str


@dataclass
class CpicGuidelineHit:
    substance_name: str
    source_file: str
    chunk_content: str
    score: float


class AdjudicationResult(BaseModel):
    interaction_detected: bool
    severity: str = Field(description="high | moderate | low | none")
    mechanism: str
    mitigation: str
    implicated_substances: list[str]


class ClinicalIRISPipeline:
    """End-to-end InterSystems IRIS Clinical RAG, LLM Adjudication & FHIR R4 Pipeline."""

    def __init__(self, fhir_base_url: str | None = None):
        conn_str = f"{config.IRIS_HOST}:{config.IRIS_PORT}/{config.IRIS_NAMESPACE}"
        self.conn = iris.connect(conn_str, config.IRIS_USER, config.IRIS_PASSWORD)
        self.embedder = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
        self.fhir_base_url = (
            fhir_base_url
            or f"http://{config.IRIS_HOST}:{config.IRIS_HTTP_PORT}/csp/healthshare/fhir/r4"
        ).rstrip("/")
        self._sukl_cache: list[tuple] | None = None

    def _load_sukl_cache(self) -> list[tuple]:
        if self._sukl_cache is None:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT SuklCode, BrandName, ActiveSubstance, SubstanceCzech, Strength, Form, AtcCode, AtcName
                FROM ClinicalData.SuklRegistry
                WHERE ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
                """
            )
            self._sukl_cache = [tuple(r) for r in cur.fetchall()]
            cur.close()
        return self._sukl_cache

    # ------------------------------------------------------------------
    # 1. Deterministic Normalization (SÚKL 7-digit code + Active Substance + WHO ATC)
    # ------------------------------------------------------------------
    def resolve_medication(self, raw_query: str) -> ResolvedMedication:
        query = raw_query.strip()
        cur = self.conn.cursor()

        # Case A: 7-digit SÚKL code
        if re.fullmatch(r"\d{7}", query):
            cur.execute(
                """
                SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, SubstanceCzech, Strength, Form, AtcCode, AtcName
                FROM ClinicalData.SuklRegistry
                WHERE SuklCode = ?
                """,
                [query],
            )
            row = cur.fetchone()
            if row is not None:
                vals = tuple(row)
                cur.close()
                return ResolvedMedication(query, *vals, match_method="exact_sukl_code")

        # Case B: Exact or prefix match on BrandName or ActiveSubstance in IRIS SQL
        first_token = re.split(r"[\s,;/()+-]+", query)[0].strip()
        cur.execute(
            """
            SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, SubstanceCzech, Strength, Form, AtcCode, AtcName
            FROM ClinicalData.SuklRegistry
            WHERE LOWER(BrandName) %STARTSWITH LOWER(?)
               OR LOWER(ActiveSubstance) = LOWER(?)
               OR LOWER(SubstanceCzech) = LOWER(?)
            ORDER BY LENGTH(BrandName) ASC
            """,
            [query, first_token, first_token],
        )
        row = cur.fetchone()
        if row is not None:
            vals = tuple(row)
            if vals[2]:
                cur.close()
                return ResolvedMedication(query, *vals, match_method="iris_sql_prefix")

        # Case B2: First-token prefix on BrandName or ActiveSubstance in IRIS SQL
        cur.execute(
            """
            SELECT TOP 1 SuklCode, BrandName, ActiveSubstance, SubstanceCzech, Strength, Form, AtcCode, AtcName
            FROM ClinicalData.SuklRegistry
            WHERE (LOWER(BrandName) %STARTSWITH LOWER(?) OR LOWER(ActiveSubstance) %STARTSWITH LOWER(?))
              AND ActiveSubstance IS NOT NULL AND ActiveSubstance <> ''
            ORDER BY LENGTH(BrandName) ASC
            """,
            [first_token, first_token],
        )
        row = cur.fetchone()
        vals = tuple(row) if row is not None else None
        cur.close()
        if vals and vals[2]:
            return ResolvedMedication(
                query, *vals, match_method="iris_sql_token_prefix"
            )

        # Case C: Levenshtein / RapidFuzz fallback across SÚKL cache
        cache = self._load_sukl_cache()
        choices = [f"{r[1]} {r[4]} ({r[2]})" for r in cache]
        best = process.extractOne(query, choices, scorer=fuzz.WRatio)
        if best and best[1] >= 60:
            idx = best[2]
            r = cache[idx]
            return ResolvedMedication(
                query, *r, match_method=f"levenshtein_fuzzy({best[1]:.0f})"
            )

        # Fallback if external unlabelled substance
        return ResolvedMedication(
            input_text=query,
            sukl_code="0000000",
            brand_name=query,
            active_substance=first_token.title(),
            substance_czech=first_token.upper(),
            strength="",
            form="",
            atc_code="",
            atc_name="",
            match_method="fallback_raw",
        )

    @staticmethod
    def canonical_substance(med: ResolvedMedication) -> str:
        """Return canonical base INN substance name (e.g., 'Tamoxifen' instead of 'Tamoxifen Citrate')."""
        if med.atc_name and len(med.atc_name.split()) == 1:
            return med.atc_name.strip().title()
        if med.active_substance:
            # Strip common salt suffixes
            cleaned = re.sub(
                r"\b(citrate|hydrochloride|hemihydrate|sodium|potassium|mesilate|mesylate|maleate|tartrate|sulfate|sulphate|acetate|calcium|dihydrate|monohydrate|anhydrous|fumarate|succinate|phosphate|besilate|besylate|bromide|chloride)\b",
                "",
                med.active_substance,
                flags=re.IGNORECASE,
            ).strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;-/")
            if cleaned:
                return cleaned.title()
        return med.active_substance.split()[0].title() if med.active_substance else ""

    # ------------------------------------------------------------------
    # 2. Deterministic Interaction Filter (DDInter Graph in IRIS SQL)
    # ------------------------------------------------------------------
    def check_deterministic_interactions(
        self, resolved_meds: list[ResolvedMedication]
    ) -> list[DeterministicDDI]:
        substances = sorted(
            {self.canonical_substance(m) for m in resolved_meds if m.active_substance}
        )
        if len(substances) < 2:
            return []

        cur = self.conn.cursor()
        hits: list[DeterministicDDI] = []
        for i in range(len(substances)):
            for j in range(i + 1, len(substances)):
                sub_a, sub_b = substances[i], substances[j]
                cur.execute(
                    """
                    SELECT TOP 1 SubstanceA, SubstanceB, RiskLevel, MechanismText
                    FROM ClinicalData.Interactions
                    WHERE (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                       OR (LOWER(SubstanceA) = LOWER(?) AND LOWER(SubstanceB) = LOWER(?))
                    """,
                    [sub_a, sub_b, sub_b, sub_a],
                )
                row = cur.fetchone()
                if row is not None:
                    hits.append(DeterministicDDI(*tuple(row)))
        cur.close()
        return hits

    # ------------------------------------------------------------------
    # 3. Guideline Semantic Retrieval (Native IRIS VECTOR_DOT_PRODUCT)
    # ------------------------------------------------------------------
    def retrieve_cpic_guidelines(
        self,
        substances: list[str],
        ddi_hits: list[DeterministicDDI],
        top_k: int = 3,
    ) -> list[CpicGuidelineHit]:
        if not substances:
            return []

        base_subs = [s.split()[0].title() for s in substances if s]
        mech_context = "; ".join(d.mechanism_text for d in ddi_hits)
        query_text = (
            f"Clinical pharmacogenomic guideline and drug interaction recommendation for "
            f"{', '.join(base_subs)}. {mech_context}"
        )
        emb = self.embedder.encode([query_text], normalize_embeddings=True)[0]
        vec_str = ",".join(f"{float(x):.6f}" for x in emb)

        cur = self.conn.cursor()
        s1 = base_subs[0]
        s2 = base_subs[1] if len(base_subs) > 1 else base_subs[0]

        # Execute the exact native IRIS VECTOR_DOT_PRODUCT SQL query
        cur.execute(
            f"""
            SELECT TOP {int(top_k)} SubstanceName, SourceFile, ChunkContent,
                   VECTOR_DOT_PRODUCT(Embedding, TO_VECTOR(?, DOUBLE, 384)) AS Score
            FROM ClinicalKnowledge.CpicVectors
            WHERE LOWER(SubstanceName) = LOWER(?) OR LOWER(SubstanceName) = LOWER(?)
            ORDER BY Score DESC
            """,
            [vec_str, s1, s2],
        )
        rows = [tuple(r) for r in cur.fetchall()]

        # If neither substance is a primary CPIC index substance, still run semantic search across all vectors
        if not rows:
            cur.execute(
                f"""
                SELECT TOP {int(top_k)} SubstanceName, SourceFile, ChunkContent,
                       VECTOR_DOT_PRODUCT(Embedding, TO_VECTOR(?, DOUBLE, 384)) AS Score
                FROM ClinicalKnowledge.CpicVectors
                ORDER BY Score DESC
                """,
                [vec_str],
            )
            rows = [tuple(r) for r in cur.fetchall()]

        cur.close()
        return [
            CpicGuidelineHit(
                substance_name=r[0],
                source_file=r[1],
                chunk_content=r[2],
                score=float(r[3]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 4. Context-Aware LLM Adjudication via Azure APIM
    # ------------------------------------------------------------------
    def adjudicate_with_llm(
        self,
        resolved_meds: list[ResolvedMedication],
        ddi_hits: list[DeterministicDDI],
        cpic_chunks: list[CpicGuidelineHit],
    ) -> AdjudicationResult:
        med_summary = [
            {
                "sukl_code": m.sukl_code,
                "brand_name": m.brand_name,
                "active_substance": self.canonical_substance(m),
                "full_salt_substance": m.active_substance,
                "atc_code": m.atc_code,
                "atc_name": m.atc_name,
            }
            for m in resolved_meds
        ]
        ddi_summary = [asdict(d) for d in ddi_hits]
        cpic_summary = [
            {
                "substance": c.substance_name,
                "source": c.source_file,
                "score": round(c.score, 4),
                "content": c.chunk_content,
            }
            for c in cpic_chunks
        ]

        prompt = (
            "You are an oncology & clinical pharmacology decision-support adjudicator.\n"
            "Analyze the normalized medications, deterministic DDInter interaction records, and retrieved CPIC guideline chunks.\n\n"
            f"Normalized Medications (SÚKL & WHO ATC):\n{json.dumps(med_summary, ensure_ascii=False, indent=2)}\n\n"
            f"Deterministic DDInter Hits:\n{json.dumps(ddi_summary, ensure_ascii=False, indent=2)}\n\n"
            f"Retrieved CPIC Vector Chunks (IRIS VECTOR_DOT_PRODUCT):\n{json.dumps(cpic_summary, ensure_ascii=False, indent=2)}\n\n"
            "Respond with ONLY valid JSON matching this exact schema:\n"
            "{\n"
            '  "interaction_detected": true,\n'
            '  "severity": "high",\n'
            '  "mechanism": "Concise clinical mechanism explaining the metabolic/pharmacogenomic or drug-drug conflict",\n'
            '  "mitigation": "Actionable clinical recommendation or alternative drug selection",\n'
            '  "implicated_substances": ["Substance1", "Substance2"]\n'
            "}"
        )

        resp = requests.post(
            f"{config.APIM_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "api-key": config.APIM_API_KEY,
            },
            json={
                "model": config.APIM_MODEL,
                "stream": False,
                "temperature": 1,
                "max_completion_tokens": 1200,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"APIM HTTP {resp.status_code}: {resp.text[:400]}")
        content = resp.json()["choices"][0]["message"]["content"]
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        parsed = json.loads(cleaned[start : end + 1])
        return AdjudicationResult.model_validate(parsed)

    # ------------------------------------------------------------------
    # 5. Direct FHIR R4 Resource Generation & Persistence
    # ------------------------------------------------------------------
    def persist_to_fhir(
        self,
        resolved_meds: list[ResolvedMedication],
        adjudication: AdjudicationResult,
        patient_ref: str = "Patient/anon-pin-session",
    ) -> dict[str, Any]:
        auth = HTTPBasicAuth(config.IRIS_USER, config.IRIS_PASSWORD)
        headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
            "Prefer": "return=representation",
        }

        created_med_statements: list[dict[str, Any]] = []
        substance_to_ref: dict[str, str] = {}

        # 1. POST MedicationStatement for each resolved medication
        for med in resolved_meds:
            coding = [
                {
                    "system": "https://sukl.cz/terminology/CodeSystem/dlp",
                    "code": med.sukl_code,
                    "display": f"{med.brand_name} {med.strength}".strip(),
                }
            ]
            if med.atc_code:
                coding.append(
                    {
                        "system": "http://www.whocc.no/atc",
                        "code": med.atc_code,
                        "display": med.atc_name or med.active_substance,
                    }
                )

            ms_resource = {
                "resourceType": "MedicationStatement",
                "status": "active",
                "medicationCodeableConcept": {
                    "coding": coding,
                    "text": f"{med.brand_name} ({med.active_substance})",
                },
                "subject": {"display": "Anonymous PIN Patient"},
            }

            r = requests.post(
                f"{self.fhir_base_url}/MedicationStatement",
                auth=auth,
                headers=headers,
                json=ms_resource,
                timeout=15,
            )
            r.raise_for_status()
            ms_id = self._extract_fhir_id(r, "MedicationStatement")
            ref = f"MedicationStatement/{ms_id}"
            canon = self.canonical_substance(med)
            created_med_statements.append(
                {
                    "id": ms_id,
                    "reference": ref,
                    "substance": canon,
                    "sukl_code": med.sukl_code,
                }
            )
            substance_to_ref[med.active_substance.lower()] = ref
            substance_to_ref[canon.lower()] = ref

        # 2. POST DetectedIssue if interaction_detected is True
        detected_issue_info = None
        if adjudication.interaction_detected:
            implicated_refs = []
            for sub in adjudication.implicated_substances:
                ref = substance_to_ref.get(sub.lower())
                if ref and {"reference": ref} not in implicated_refs:
                    implicated_refs.append({"reference": ref, "display": sub})
            if not implicated_refs:
                implicated_refs = [
                    {"reference": m["reference"], "display": m["substance"]}
                    for m in created_med_statements
                ]

            di_resource = {
                "resourceType": "DetectedIssue",
                "status": "final",
                "severity": "high"
                if adjudication.severity.lower() in ("high", "major", "critical")
                else adjudication.severity.lower(),
                "code": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": "DRG",
                            "display": "Drug Interaction Alert",
                        }
                    ]
                },
                "implicated": implicated_refs,
                "detail": f"Mechanism: {adjudication.mechanism} | Mitigation: {adjudication.mitigation}",
                "mitigation": [
                    {
                        "action": {
                            "text": adjudication.mitigation,
                        }
                    }
                ],
            }

            r_di = requests.post(
                f"{self.fhir_base_url}/DetectedIssue",
                auth=auth,
                headers=headers,
                json=di_resource,
                timeout=15,
            )
            r_di.raise_for_status()
            di_id = self._extract_fhir_id(r_di, "DetectedIssue")
            detected_issue_info = {
                "id": di_id,
                "reference": f"DetectedIssue/{di_id}",
                "resource": di_resource,
            }

        return {
            "fhir_base_url": self.fhir_base_url,
            "medication_statements": created_med_statements,
            "detected_issue": detected_issue_info,
        }

    @staticmethod
    def _extract_fhir_id(resp: requests.Response, resource_type: str) -> str:
        if resp.text:
            try:
                body = resp.json()
                if "id" in body:
                    return str(body["id"])
            except Exception:
                pass
        loc = resp.headers.get("Location") or resp.headers.get("Content-Location") or ""
        m = re.search(rf"{resource_type}/([^/_?#]+)", loc)
        return m.group(1) if m else "unknown"
