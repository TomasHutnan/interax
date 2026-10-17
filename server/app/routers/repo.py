"""FHIR R4 repository upload endpoint (/repo)."""

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.prescriptions import Prescription

try:
    from rag import upload_to_fhir
except ModuleNotFoundError:
    from server.rag import upload_to_fhir

router = APIRouter(tags=["repo"])


class RepoUploadRequest(BaseModel):
    meds: list[Prescription]
    interactions: list[tuple[str, str, str, str]] = []


@router.post("/repo")
@router.post("/api/repo")
def upload_repo(payload: RepoUploadRequest) -> dict[str, object]:
    """Upload prescriptions (MedicationStatement) and interactions (DetectedIssue) to the IRIS FHIR R4 database."""
    try:
        return upload_to_fhir(
            meds=[m.model_dump() for m in payload.meds],
            interactions=payload.interactions,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"FHIR server error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Repository upload failed: {exc}",
        ) from exc
