"""Image ingestion endpoints wrapping the OCR modules in `server/ocr/`.

Endpoints are sync (`def`) on purpose: the OCR calls use blocking `requests`,
so FastAPI runs them in its threadpool instead of blocking the event loop.
"""

from fastapi import APIRouter, HTTPException, UploadFile
from ocr import handwritten, package

router = APIRouter(prefix="/scan", tags=["scan"])


def _read_image(file: UploadFile) -> bytes:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="expected an image upload")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    return data


@router.post("/package")
def scan_package(file: UploadFile) -> dict:
    try:
        return package.process_medication(_read_image(file))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/handwritten")
def scan_handwritten(file: UploadFile) -> list[dict]:
    try:
        return handwritten.process_medication(_read_image(file))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
