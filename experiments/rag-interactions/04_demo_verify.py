"""Phase 5: End-to-End Verification & Demo Workflow on InterSystems IRIS."""

import importlib
import json

import requests
from requests.auth import HTTPBasicAuth

import config

pipeline_mod = importlib.import_module("03_pipeline")
ClinicalIRISPipeline = pipeline_mod.ClinicalIRISPipeline


def run_scenario(pipeline: ClinicalIRISPipeline, title: str, drug_inputs: list[str]):
    print("=" * 80)
    print(f"SCENARIO: {title}")
    print(f"Input Drug Strings: {drug_inputs}")
    print("=" * 80)

    # Step 1: SÚKL & WHO ATC Deterministic Normalization
    print("\n[1] Deterministic Normalization (ClinicalData.SuklRegistry in IRIS):")
    resolved = [pipeline.resolve_medication(d) for d in drug_inputs]
    for m in resolved:
        print(
            f"  • '{m.input_text}' -> SÚKL: {m.sukl_code} | Brand: {m.brand_name} {m.strength} "
            f"| Active Substance: {m.active_substance} | WHO ATC: {m.atc_code} ({m.atc_name}) [{m.match_method}]"
        )

    # Step 2: Deterministic Interaction Filter (DDInter Graph)
    print("\n[2] Deterministic Interaction Filter (ClinicalData.Interactions in IRIS):")
    ddi_hits = pipeline.check_deterministic_interactions(resolved)
    for h in ddi_hits:
        print(
            f"  • [{h.risk_level}] {h.substance_a} + {h.substance_b}: {h.mechanism_text}"
        )

    # Step 3: Native Vector Similarity Search (VECTOR_DOT_PRODUCT on ClinicalKnowledge.CpicVectors)
    print("\n[3] Guideline Semantic Retrieval (IRIS SQL VECTOR_DOT_PRODUCT TOP 3):")
    substances = [m.active_substance for m in resolved if m.active_substance]
    cpic_hits = pipeline.retrieve_cpic_guidelines(substances, ddi_hits, top_k=3)
    for idx, c in enumerate(cpic_hits, 1):
        snippet = c.chunk_content[:220] + ("..." if len(c.chunk_content) > 220 else "")
        print(
            f"  • Top {idx} (Score={c.score:.4f} | Substance={c.substance_name} | Source={c.source_file}):"
        )
        print(f'    "{snippet}"')

    # Step 4: Context-Aware LLM Adjudication via Azure APIM
    print(f"\n[4] Context-Aware LLM Adjudication (APIM Model: {config.APIM_MODEL}):")
    adjudication = pipeline.adjudicate_with_llm(resolved, ddi_hits, cpic_hits)
    print(json.dumps(adjudication.model_dump(), indent=2, ensure_ascii=False))

    # Step 5: Direct FHIR R4 Persistence
    print(f"\n[5] Direct FHIR R4 Persistence ({pipeline.fhir_base_url}):")
    fhir_out = pipeline.persist_to_fhir(resolved, adjudication)
    for ms in fhir_out["medication_statements"]:
        print(
            f"  • Created FHIR MedicationStatement: {ms['reference']} (SÚKL DLP={ms['sukl_code']}, {ms['substance']})"
        )
    if fhir_out["detected_issue"]:
        di = fhir_out["detected_issue"]
        print(
            f"  • Created FHIR DetectedIssue:       {di['reference']} (severity=high, status=final)"
        )
    print()


def verify_fhir_query(fhir_base_url: str):
    print("=" * 80)
    print(f"FHIR QUERY VERIFICATION: GET {fhir_base_url}/DetectedIssue?severity=high")
    print("=" * 80)
    auth = HTTPBasicAuth(config.IRIS_USER, config.IRIS_PASSWORD)
    r = requests.get(
        f"{fhir_base_url}/DetectedIssue?severity=high",
        auth=auth,
        headers={"Accept": "application/fhir+json"},
        timeout=15,
    )
    r.raise_for_status()
    bundle = r.json()
    entries = [
        e.get("resource", {})
        for e in bundle.get("entry", [])
        if e.get("resource", {}).get("resourceType") == "DetectedIssue"
    ]
    print(
        f"HTTP {r.status_code} OK — Total high-severity DetectedIssue resources in FHIR Server: {len(entries)}"
    )
    for res in entries[:5]:
        implicated = [imp.get("reference") for imp in res.get("implicated", [])]
        print(
            f"  • ID: DetectedIssue/{res.get('id')} | status={res.get('status')} | severity={res.get('severity')} "
            f"| implicated={implicated}"
        )
        print(f"    detail: {res.get('detail')}")


if __name__ == "__main__":
    pipe = ClinicalIRISPipeline()
    # Scenario 1: Tamoxifen + Paroxetine (CYP2D6 bioactivation block)
    run_scenario(
        pipe,
        "Oncological CYP2D6 Conflict (Tamoxifen + Paroxetine)",
        ["TAMOXIFEN EBEWE 20MG", "PAROXETIN +PHARMA 20MG"],
    )
    # Scenario 2: Capecitabine + Brivudine (DPYD lethal fluoropyrimidine toxicity)
    run_scenario(
        pipe,
        "Oncological DPYD Fluoropyrimidine Conflict (Capecitabine + Brivudine)",
        ["CAPECITABINE ACCORD 500MG", "BRIVUDIN"],
    )
    verify_fhir_query(pipe.fhir_base_url)
