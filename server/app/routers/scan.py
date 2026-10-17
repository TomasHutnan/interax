"""Image ingestion endpoint wrapping the OCR modules in `server/ocr/`.

The endpoint is sync (`def`) on purpose: the OCR calls use blocking `requests`,
so FastAPI runs it in its threadpool instead of blocking the event loop.
"""

from typing import Annotated, Literal

import requests
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from ocr import auto
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.prescriptions import Prescription, lookup_prescription, merge_prescriptions

router = APIRouter(prefix="/scan", tags=["scan"])

_meds_adapter = TypeAdapter(list[Prescription])


class ScanResponse(BaseModel):
    kind: Literal["package", "handwritten"]
    meds: list[Prescription]


def _resolve(
    conn: Connection[DictRow], name: str, usage: str = "", query: str | None = None
) -> Prescription:
    """SÚKL match for `query` (default: `name`); falls back to `name` without substances."""
    return lookup_prescription(conn, query or name, usage) or Prescription(
        drug=name, usage=usage
    )


@router.post("")
def scan(
    request: Request,
    file: UploadFile,
    meds: Annotated[str, Form(description="Current prescriptions, as a JSON array")],
) -> ScanResponse:
    """Digitize one medication image and apply it to the current prescription list.

    The model decides whether the image shows packaging or a handwritten list.
    Each medication read from it is matched against SÚKL; medications already in
    `meds` get their usage (and, if matched, `mg`/`subs`) updated, new ones are
    appended. Returns the updated list.
    """
    try:
        current = _meds_adapter.validate_json(meds)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="expected an image upload")
    image = file.file.read()
    if not image:
        raise HTTPException(status_code=400, detail="empty file")

    try:
        result = auto.scan(image, mime_type=content_type)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="OCR model unreachable") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Connection taken only after OCR, so the slow model call doesn't hold one.
    with request.app.state.pool.connection() as conn:
        if isinstance(result, auto.PackageResult):
            name = result.brandName or result.genericName
            query = " ".join(filter(None, [name, result.strength]))
            scanned = [_resolve(conn, name, result.usage or "", query=query)] if name else []
        else:
            scanned = [
                _resolve(conn, med.name, med.usage or "") for med in result.medications
            ]

    return ScanResponse(kind=result.kind, meds=merge_prescriptions(current, scanned))
