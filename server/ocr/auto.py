"""Unified medication OCR: one image in, the model decides what it shows.

A single model call both classifies the image (packaging vs handwritten list)
and extracts the matching structure; the result's `kind` says which one.
"""

import base64
import re
from typing import Annotated, Literal

import requests
from ocr import package
from pydantic import BaseModel, Field, TypeAdapter, field_validator

PROMPT = (
    "First decide what the image shows:\n"
    '- "package": printed medication packaging (box, blister, bottle, label, leaflet), '
    "even if a pharmacist or doctor has written dosing instructions on it by hand.\n"
    '- "handwritten": a list or schedule of medications written on paper '
    "(handwritten or printed), possibly with several medications.\n"
    "Then extract the information for that kind.\n"
    "Whenever you come across text that's provided in multiple languages make sure to choose only ONE language and prioritize Czech language.\n"
    "For package: the brand (trade) name, generic name, active substance(s), strength "
    "(e.g. 500 mg), dosage form (e.g. tablets, syrup), quantity (e.g. 20 tablets) and "
    "manufacturer. Normalize the brand/generic name. If a field is not visible, use null.\n"
    "Also look for dosing instructions added to the package by hand or on a sticker, "
    'usually by the pharmacist (e.g. "1-0-1", "3x denně", "ráno 1"). Return them as '
    "usage, normalized to the notations described under handwritten below. Printed "
    "text such as the leaflet's general dosage advice is NOT usage. If there is no "
    'such note, use "".\n'
    "For handwritten: read ALL medications, one entry per medication, in the order they "
    "appear. Do not skip lines, do not merge different medications, and do not invent "
    "entries. If no medication is visible, return an empty list. For each medication extract:\n"
    "- name: the medication name as written, including the strength if written "
    '(e.g. "Prestarium Neo 5 mg").\n'
    "- usage: how the medication is taken, written in one of three notations. "
    "Return it normalized to that notation:\n"
    '  1. "a-b-c" (e.g. "1-0-1", "1/2-0-2"): pieces in the morning, at noon and in '
    'the evening -> return e.g. "1-0-1".\n'
    '  2. "á n dní" / "á n dny" (one piece every n days; the accent on "á" may be '
    'missing) -> return e.g. "á 2 dny".\n'
    '  3. "kx" or "k*" (e.g. "3x", "3*", "2x denně"; k times a day, no set time) '
    '-> return e.g. "3x".\n'
    '  If no usage is written, or it matches none of these notations, use "". Do not guess.\n'
    "Keep text in the original language. "
    "Respond with ONLY valid JSON, no commentary, in exactly one of these shapes:\n"
    '{"kind":"package","brandName":"string","genericName":"string or null",'
    '"activeSubstance":"string","strength":"string","dosageForm":"string",'
    '"quantity":"string","manufacturer":"string","usage":"string"}\n'
    '{"kind":"handwritten","medications":[{"name":"string","usage":"string"}]}'
)

# "3*" / "3 ×" -> "3x": the times-a-day notation is shown as "kx", whatever the model returns.
_TIMES_A_DAY = re.compile(r"(\d)\s*[*×]")


def normalize_usage(usage: str | None) -> str | None:
    return _TIMES_A_DAY.sub(r"\1x", usage) if usage else usage


class HandwrittenMedication(BaseModel):
    # Optional so one nameless entry from the model doesn't fail the whole result;
    # callers skip entries without a name.
    name: str | None = None
    usage: str | None = (
        None  # tolerate null from the model; normalized to "" downstream
    )

    @field_validator("usage")
    @classmethod
    def times_a_day_as_x(cls, usage: str | None) -> str | None:
        return normalize_usage(usage)


class PackageResult(BaseModel):
    """Only the fields needed to look the product up; the model may omit any of them."""

    kind: Literal["package"] = "package"
    brandName: str | None = None
    genericName: str | None = None
    strength: str | None = None
    usage: str | None = None  # pharmacist's handwritten dosing note, if any

    @field_validator("usage")
    @classmethod
    def times_a_day_as_x(cls, usage: str | None) -> str | None:
        return normalize_usage(usage)


class HandwrittenResult(BaseModel):
    kind: Literal["handwritten"] = "handwritten"
    medications: list[HandwrittenMedication] = Field(default_factory=list)


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
