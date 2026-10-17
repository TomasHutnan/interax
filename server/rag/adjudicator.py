"""Azure APIM LLM adjudication and strict output sanitization."""

import json
import logging
import re

import requests

from rag.config import (
    APIM_API_KEY,
    APIM_BASE_URL,
    APIM_MODEL,
    AdjudicatedPair,
    ResolvedMed,
)

log = logging.getLogger("uvicorn.error")

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

_UNKNOWN_RE = re.compile(
    r"^(unknown|not\s+available|unavailable|not\s+specified|unspecified|"
    r"no\s+available\s+info\w*|no\s+information\b.*|n/?a|none)\b",
    re.IGNORECASE,
)


def enforce_concise_text(text: str, max_words: int = 10) -> str:
    """Strip unknown placeholders to empty string and cap valid text at max_words."""
    cleaned = text.strip()
    if not cleaned or _UNKNOWN_RE.match(cleaned) or "unknown" in cleaned.lower():
        return ""
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _build_user_payload(
    resolved: list[ResolvedMed],
    ddi_hits: list[dict[str, str]],
    cpic_chunks: list[dict[str, object]],
) -> str:
    return json.dumps(
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


def _parse_llm_json(raw_content: str | None) -> dict[str, object] | None:
    """Extract the JSON object from the reply; None if there isn't a usable one."""
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_content or "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def adjudicate_interactions(
    resolved: list[ResolvedMed],
    ddi_hits: list[dict[str, str]],
    cpic_chunks: list[dict[str, object]],
) -> dict[str, AdjudicatedPair]:
    """Call Azure APIM to synthesize <=10-word mechanism and consequence per pairing.

    Returns {} when the model gives no usable answer, so callers fall back to the
    deterministic DDInter text instead of failing the whole interaction check.
    """
    resp = requests.post(
        f"{APIM_BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "api-key": APIM_API_KEY},
        json={
            "model": APIM_MODEL,
            "stream": False,
            "temperature": 1,
            # Reasoning models spend hidden tokens before answering; too small a
            # budget yields an empty `content` with finish_reason="length".
            "max_completion_tokens": 6000,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_payload(resolved, ddi_hits, cpic_chunks),
                },
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    choice = (resp.json().get("choices") or [{}])[0]
    parsed = _parse_llm_json((choice.get("message") or {}).get("content"))
    if parsed is None:
        log.warning(
            "adjudicator returned no usable JSON (finish_reason=%s); using DDInter text",
            choice.get("finish_reason"),
        )
        return {}

    adjudications: dict[str, AdjudicatedPair] = {}
    for pair_key, val in parsed.items():
        if not isinstance(val, dict):
            continue
        if (
            "pathophysiological_mechanism" not in val
            or "clinical_consequence" not in val
        ):
            continue
        adjudications[pair_key] = AdjudicatedPair(
            pathophysiological_mechanism=enforce_concise_text(
                str(val["pathophysiological_mechanism"]), 10
            ),
            clinical_consequence=enforce_concise_text(
                str(val["clinical_consequence"]), 10
            ),
        )
    return adjudications
