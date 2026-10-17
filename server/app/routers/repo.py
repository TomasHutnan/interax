"""FHIR R4 repository upload endpoint (/api/repo)."""

import logging
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.prescriptions import Prescription

try:
    from rag import upload_to_fhir
    from rag.pipeline import IRIS_HOST
except ModuleNotFoundError:
    from server.rag import upload_to_fhir
    from server.rag.pipeline import IRIS_HOST

log = logging.getLogger("uvicorn.error")

# Clinician-only: this writes into the shared FHIR repository.
router = APIRouter(
    prefix="/api/repo", tags=["repo"], dependencies=[Depends(require_user)]
)

Severity = Literal["contraindicated", "major", "moderate", "minor", "unknown"]


class RepoUploadRequest(BaseModel):
    meds: list[Prescription] = Field(max_length=200)
    # [substance_1, substance_2, description, severity], substances by name.
    interactions: list[tuple[str, str, str, Severity]] = Field(
        default=[], max_length=500
    )


@router.post("")
def upload_repo(payload: RepoUploadRequest) -> dict[str, object]:
    """Upload prescriptions (MedicationStatement) and interactions (DetectedIssue) to the IRIS FHIR R4 database."""
    if not IRIS_HOST:
        raise HTTPException(status_code=503, detail="repository not configured")
    try:
        return upload_to_fhir(
            meds=[m.model_dump() for m in payload.meds],
            interactions=[(a, b, d, str(s)) for a, b, d, s in payload.interactions],
        )
    except requests.RequestException as exc:
        log.exception("FHIR upload failed")
        raise HTTPException(status_code=502, detail="FHIR server error") from exc
    except Exception as exc:
        log.exception("repository upload failed")
        raise HTTPException(status_code=500, detail="Repository upload failed") from exc
