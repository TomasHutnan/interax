"""Handwritten medication-list OCR via the OpenAI-compatible endpoint.

Port of ocr_handwritten.js. Usage:
    from ocr_handwritten import process_medication
    meds = process_medication(open("img.jpg", "rb").read())
    python ocr_handwritten.py img.jpg
"""

import base64
import json
import os
import re
import sys

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

BASE_URL = os.getenv("UNSLOTH_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
API_KEY = os.getenv("UNSLOTH_API_KEY", "none")
MODEL = os.getenv("UNSLOTH_MODEL", "")

PROMPT = (
    "The image may contain several lines of text listing multiple medications. "
    "Read ALL of them, one entry per medication, in the order they appear. "
    "For each, extract the name and dosage (strength and/or frequency if shown, otherwise null). "
    "Do not skip lines, do not merge different medications, and do not invent entries. "
    "Keep text in the original language. If no medication is visible, return an empty list. "
    "Respond with ONLY valid JSON, no commentary, in exactly this shape: "
    '{"medications":[{"name":"string","dosage":"string or null"}]}'
)


class Medication(BaseModel):
    name: str
    dosage: str | None = None


class MedicationList(BaseModel):
    medications: list[Medication] = Field(default_factory=list)


def extract_json(text: str) -> dict:
    cleaned = re.sub(r"<think>[\s\S]*?<\/think>", "", text, flags=re.I)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model output: {text[:300]}")
    return json.loads(cleaned[start : end + 1])


_model_id = None


def resolve_model() -> str:
    global _model_id
    if MODEL:
        return MODEL
    if _model_id is None:
        r = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {API_KEY}", "api-key": API_KEY},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data") or []
        if not data:
            raise RuntimeError("Server reports no loaded model.")
        _model_id = data[0]["id"]
    return _model_id


def process_medication(image: bytes | None = None) -> list[dict]:
    image_base64 = (
        base64.b64encode(image).decode()
        if image
        else base64.b64encode(open("req-tmp.jpg", "rb").read()).decode()
    )
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "api-key": API_KEY},
        json={
            "model": resolve_model(),
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
                                "url": f"data:image/jpeg;base64,{image_base64}"
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

    return [
        m.model_dump()
        for m in MedicationList.model_validate(extract_json(text)).medications
    ]


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else None
    print(json.dumps(process_medication(data), ensure_ascii=False, indent=2))
