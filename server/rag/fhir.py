"""HL7 FHIR R4 persistence for MedicationStatement and DetectedIssue resources."""

import uuid

import requests
from requests.auth import HTTPBasicAuth

from rag.config import (
    IRIS_HOST,
    IRIS_HTTP_PORT,
    IRIS_PASSWORD,
    IRIS_USER,
    ResolvedMed,
    get_iris_connection,
)
from rag.iris_store import resolve_medications

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

_FHIR_HEADERS = {
    "Content-Type": "application/fhir+json",
    "Accept": "application/fhir+json",
    "Prefer": "return=representation",
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


def _resolve_med_list(meds: list[dict[str, object]]) -> list[ResolvedMed]:
    if not meds:
        return []
    queries: list[str] = []
    for m in meds:
        drug = str(m.get("drug") or "").strip()
        subs = [str(s).strip() for s in (m.get("subs") or []) if str(s).strip()]
        queries.append(drug or (subs[0] if subs else "Unknown"))

    conn = get_iris_connection()
    try:
        return resolve_medications(conn, queries)
    finally:
        conn.close()


def _build_medication_statement(
    med: dict[str, object],
    resolved: ResolvedMed,
    subject_ref: str,
) -> tuple[dict[str, object], str, list[str]]:
    drug = str(med.get("drug") or resolved.brand_name).strip()
    mg = str(med.get("mg") or "").strip()
    subs = [str(s).strip() for s in (med.get("subs") or []) if str(s).strip()]
    usage = str(med.get("usage") or "").strip()

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
    payload: dict[str, object] = {
        "resourceType": "MedicationStatement",
        "status": "active",
        "medicationCodeableConcept": {
            "coding": coding,
            "text": f"{drug} ({subs_label})" if subs_label else drug,
        },
        "subject": {"reference": subject_ref},
    }

    mg_label = f"{mg} mg" if mg and mg.replace(".", "").replace("/", "").isdigit() else mg
    dosage_parts = [p for p in (mg_label, usage) if p]
    if dosage_parts:
        payload["dosage"] = [{"text": " | ".join(dosage_parts)}]

    index_keys = [drug, resolved.canonical_name, resolved.active_substance, *subs]
    return payload, drug, index_keys


def _post_detected_issue(
    base_url: str,
    auth: HTTPBasicAuth,
    payload: dict[str, object],
) -> requests.Response:
    resp = requests.post(
        f"{base_url}/DetectedIssue",
        auth=auth,
        headers=_FHIR_HEADERS,
        json=payload,
        timeout=10,
    )
    if resp.status_code == 400 and "UnexpectedPropertyName" in resp.text:
        r4_payload = {k: v for k, v in payload.items() if k != "subject"}
        r4_payload["patient"] = payload["subject"]
        resp = requests.post(
            f"{base_url}/DetectedIssue",
            auth=auth,
            headers=_FHIR_HEADERS,
            json=r4_payload,
            timeout=10,
        )
    resp.raise_for_status()
    return resp


def upload_to_fhir(
    meds: list[dict[str, object]],
    interactions: list[tuple[str, str, str, str]],
) -> dict[str, object]:
    """Upload prescriptions (MedicationStatement) and interactions (DetectedIssue) to IRIS FHIR R4."""
    session_uuid = str(uuid.uuid4())
    subject_ref = f"Patient/{session_uuid}"
    base_url = f"http://{IRIS_HOST}:{IRIS_HTTP_PORT}/csp/healthshare/fhir/r4"
    auth = HTTPBasicAuth(IRIS_USER, IRIS_PASSWORD)

    resolved_list = _resolve_med_list(meds)
    sub_to_ref: dict[str, str] = {}
    created_meds: list[dict[str, object]] = []

    for med, resolved in zip(meds, resolved_list):
        ms_payload, drug, index_keys = _build_medication_statement(med, resolved, subject_ref)
        resp = requests.post(
            f"{base_url}/MedicationStatement",
            auth=auth,
            headers=_FHIR_HEADERS,
            json=ms_payload,
            timeout=10,
        )
        resp.raise_for_status()
        ms_id = str(resp.json().get("id", "unknown"))
        ref = f"MedicationStatement/{ms_id}"

        for key in index_keys:
            if key and key.strip():
                sub_to_ref[key.strip().lower()] = ref

        created_meds.append(
            {
                "id": ms_id,
                "reference": ref,
                "drug": drug,
                "sukl_code": resolved.sukl_code,
                "status_code": resp.status_code,
            }
        )

    created_issues: list[dict[str, object]] = []
    for sub1, sub2, description, severity in interactions:
        fhir_severity = _FHIR_SEVERITY_MAP.get(str(severity).strip().lower(), "high")
        implicated = [
            {"reference": ref, "display": s}
            for s in (sub1, sub2)
            if (ref := _match_med_ref(s, sub_to_ref)) is not None
        ]
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
        resp_di = _post_detected_issue(base_url, auth, di_payload)
        di_id = str(resp_di.json().get("id", "unknown"))
        created_issues.append(
            {
                "id": di_id,
                "reference": f"DetectedIssue/{di_id}",
                "substances": [sub1, sub2],
                "severity": fhir_severity,
                "status_code": resp_di.status_code,
            }
        )

    return {
        "session_uuid": session_uuid,
        "subject_reference": subject_ref,
        "medication_statements": created_meds,
        "detected_issues": created_issues,
    }
