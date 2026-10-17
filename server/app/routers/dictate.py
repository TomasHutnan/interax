"""Dictation endpoint: spoken (or already transcribed) medication list -> prescriptions.

Sync (`def`) for the same reason as `/api/scan`: Whisper and the model call block,
so FastAPI runs this in its threadpool instead of blocking the event loop.
"""

from typing import Annotated

import requests
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from ocr import dictation
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.prescriptions import Prescription, lookup_prescription, merge_prescriptions

router = APIRouter(prefix="/api/dictate", tags=["dictate"])

_meds_adapter = TypeAdapter(list[Prescription])

# Several minutes of compressed audio; local CPU transcription of more would take ages.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class DictateResponse(BaseModel):
    transcript: str
    meds: list[Prescription]


@router.post("")
def dictate(
    request: Request,
    meds: Annotated[str, Form(description="Current prescriptions, as a JSON array")],
    file: UploadFile | None = None,
    text: Annotated[
        str | None, Form(description="Transcript, if already transcribed elsewhere")
    ] = None,
) -> DictateResponse:
    """Turn a dictated medication list into prescriptions and merge it into `meds`.

    Send either `file` (audio, transcribed locally by Whisper) or `text` (a transcript).
    The transcript is returned so the user can check what was understood.
    """
    try:
        current = _meds_adapter.validate_json(meds)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc

    text = (text or "").strip()
    if (file is None) == (not text):
        raise HTTPException(
            status_code=422, detail="send exactly one of `file` or `text`"
        )

    if file is not None:
        content_type = file.content_type or ""
        # Browsers' MediaRecorder sometimes labels audio-only webm/mp4 as video/*.
        if not content_type.startswith(("audio/", "video/")):
            raise HTTPException(status_code=415, detail="expected an audio upload")
        audio = file.file.read()
        if not audio:
            raise HTTPException(status_code=400, detail="empty file")
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="audio larger than 25 MB")
        try:
            text = dictation.transcribe(audio)
        except Exception as exc:  # PyAV/ctranslate2 raise assorted types on bad audio
            raise HTTPException(
                status_code=400, detail=f"could not transcribe audio: {exc}"
            ) from exc

    try:
        dictated = dictation.extract(text) if text else []
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="model unreachable") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Connection taken only after the slow steps, so they don't hold one.
    with request.app.state.pool.connection() as conn:
        scanned = [
            lookup_prescription(conn, med.name, med.usage or "")
            or Prescription(drug=med.name, usage=med.usage or "")
            for med in dictated
            if med.name and med.name.strip()
        ]

    return DictateResponse(transcript=text, meds=merge_prescriptions(current, scanned))
