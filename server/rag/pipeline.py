"""High-level orchestration for the InterSystems IRIS Clinical RAG pipeline."""

import logging

import requests

from rag.adjudicator import adjudicate_interactions, enforce_concise_text
from rag.config import AdjudicatedPair, RagInteraction, ResolvedMed, get_iris_connection
from rag.fhir import upload_to_fhir
from rag.iris_store import (
    query_ddinter_interactions,
    resolve_medications,
    retrieve_cpic_chunks,
)

__all__ = ["RagInteraction", "check_rag_interactions", "upload_to_fhir"]

log = logging.getLogger("uvicorn.error")


def _fetch_iris_context(
    substances: list[str],
) -> tuple[list[ResolvedMed], list[dict[str, str]], list[dict[str, object]]]:
    """Resolve medications, query DDInter interactions, and retrieve CPIC vector chunks."""
    conn = get_iris_connection()
    try:
        resolved = resolve_medications(conn, substances)
        unique_canons = sorted({m.canonical_name for m in resolved if m.canonical_name})
        if len(unique_canons) < 2:
            return resolved, [], []

        cur = conn.cursor()
        try:
            ddi_hits = query_ddinter_interactions(cur, unique_canons)
            if not ddi_hits:
                return resolved, [], []
            cpic_chunks = retrieve_cpic_chunks(cur, unique_canons, ddi_hits)
            return resolved, ddi_hits, cpic_chunks
        finally:
            cur.close()
    finally:
        conn.close()


def _map_adjudicated_results(
    resolved: list[ResolvedMed],
    ddi_hits: list[dict[str, str]],
    adjudications: dict[str, AdjudicatedPair],
) -> list[RagInteraction]:
    canon_to_input = {m.canonical_name.lower(): m.input_text for m in resolved}
    results: list[RagInteraction] = []

    for hit in ddi_hits:
        pair_key = hit["pairing"]
        rev_key = f"{hit['substance_b']} + {hit['substance_a']}"
        adj = adjudications.get(pair_key) or adjudications.get(rev_key)

        mech = (
            adj.pathophysiological_mechanism
            if adj is not None
            else enforce_concise_text(hit["mechanism_text"], 10)
        )
        conseq = adj.clinical_consequence if adj is not None else ""

        in_1 = canon_to_input.get(hit["substance_a"].lower(), hit["substance_a"])
        in_2 = canon_to_input.get(hit["substance_b"].lower(), hit["substance_b"])
        results.append(
            RagInteraction(
                substance_1=in_1,
                substance_2=in_2,
                pathophysiological_mechanism=mech,
                clinical_consequence=conseq,
                severity=hit["risk_level"].lower(),
            )
        )

    return results


def check_rag_interactions(substances: list[str]) -> list[RagInteraction]:
    """Run the IRIS SQL + Vector RAG + Azure APIM adjudication pipeline."""
    if len(substances) < 2:
        return []

    resolved, ddi_hits, cpic_chunks = _fetch_iris_context(substances)
    if not ddi_hits:
        return []

    # The LLM only rewords the DDInter hits; if it's down, still return the hits.
    try:
        adjudications = adjudicate_interactions(resolved, ddi_hits, cpic_chunks)
    except requests.RequestException:
        log.exception("adjudicator request failed; using DDInter text")
        adjudications = {}
    return _map_adjudicated_results(resolved, ddi_hits, adjudications)
