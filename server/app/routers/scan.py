"""Image ingestion endpoint wrapping the OCR modules in `server/ocr/`.

The endpoint is sync (`def`) on purpose: the OCR calls use blocking `requests`,
so FastAPI runs it in its threadpool instead of blocking the event loop.
"""

from typing import Annotated, Literal

import requests
from fastapi import APIRouter, HTTPException, Request, UploadFile
from ocr import auto
from pydantic import BaseModel, Field

from app.prescriptions import Prescription, lookup_prescription

router = APIRouter(prefix="/scan", tags=["scan"])


class HandwrittenScan(BaseModel):
    kind: Literal["handwritten"] = "handwritten"
    prescriptions: list[Prescription]


ScanResponse = Annotated[
    auto.PackageResult | HandwrittenScan, Field(discriminator="kind")
]


@router.post("")
def scan(request: Request, file: UploadFile) -> ScanResponse:
    """Digitize one medication image.

    The model decides whether it shows packaging or a handwritten list; the
    response's `kind` field says which shape was returned. Handwritten entries are
    matched against SÚKL to get the product name and its active substances; when no
    product matches, `drug` is the name as read and `subs` is empty.
    """
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

    if isinstance(result, auto.PackageResult):
        return result

    # Connection taken only after OCR, so the slow model call doesn't hold one.
    with request.app.state.pool.connection() as conn:
        prescriptions = []
        for med in result.medications:
            usage = med.usage or ""
            prescriptions.append(
                lookup_prescription(conn, med.name, usage)
                or Prescription(drug=med.name, subs=[], usage=usage)
            )
    return HandwrittenScan(prescriptions=prescriptions)
