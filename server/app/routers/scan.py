"""Image ingestion endpoint wrapping the OCR modules in `server/ocr/`.

The endpoint is sync (`def`) on purpose: the OCR calls use blocking `requests`,
so FastAPI runs it in its threadpool instead of blocking the event loop.
"""

import requests
from fastapi import APIRouter, HTTPException, UploadFile
from ocr import auto

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("")
def scan(file: UploadFile) -> auto.ScanResult:
    """Digitize one medication image.

    The model decides whether it shows packaging or a handwritten list; the
    response's `kind` field says which shape was returned.
    """
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="expected an image upload")
    image = file.file.read()
    if not image:
        raise HTTPException(status_code=400, detail="empty file")

    try:
        return auto.scan(image, mime_type=content_type)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="OCR model unreachable") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
