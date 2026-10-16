"""Unified medication OCR: one image in, the model decides what it shows.

A single model call both classifies the image (packaging vs handwritten list)
and extracts the matching structure; the result's `kind` says which one.
"""

import base64
from typing import Annotated, Literal

import requests
from ocr import handwritten, package
from pydantic import Field, TypeAdapter

PROMPT = (
    "First decide what the image shows:\n"
    '- "package": printed medication packaging (box, blister, bottle, label, leaflet).\n'
    '- "handwritten": a list or schedule of medications written on paper '
    "(handwritten or printed), possibly with several medications.\n"
    "Then extract the information for that kind.\n"
    "For package: the brand (trade) name, generic name, active substance(s), strength "
    "(e.g. 500 mg), dosage form (e.g. tablets, syrup), quantity (e.g. 20 tablets) and "
    "manufacturer. Normalize the brand/generic name. If a field is not visible, use null.\n"
    "For handwritten: read ALL medications, one entry per medication, in the order they "
    "appear, with name and dosage (strength and/or frequency if shown, otherwise null). "
    "Do not skip lines, do not merge different medications, and do not invent entries. "
    "If no medication is visible, return an empty list.\n"
    "Keep text in the original language. "
    "Respond with ONLY valid JSON, no commentary, in exactly one of these shapes:\n"
    '{"kind":"package","brandName":"string","genericName":"string or null",'
    '"activeSubstance":"string","strength":"string","dosageForm":"string",'
    '"quantity":"string","manufacturer":"string"}\n'
    '{"kind":"handwritten","medications":[{"name":"string","dosage":"string or null"}]}'
)


class PackageResult(package.MedicationPackaging):
    kind: Literal["package"] = "package"


class HandwrittenResult(handwritten.MedicationList):
    kind: Literal["handwritten"] = "handwritten"


ScanResult = Annotated[PackageResult | HandwrittenResult, Field(discriminator="kind")]

_scan_result = TypeAdapter(ScanResult)


def scan(
    image: bytes, mime_type: str = "image/jpeg"
) -> PackageResult | HandwrittenResult:
    image_base64 = base64.b64encode(image).decode()
    resp = requests.post(
        f"{package.BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "api-key": package.API_KEY},
        json={
            "model": package.resolve_model(),
            "stream": False,
            "temperature": 1,
            "max_completion_tokens": 1500,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
        },
        timeout=180,
    )
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    text = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content")
    if not text:
        raise RuntimeError("No response text received from the model.")

    return _scan_result.validate_python(package.extract_json(text))
