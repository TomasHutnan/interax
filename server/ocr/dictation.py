"""Dictated medication lists: audio -> transcript -> [{name, usage}].

The chat model can't take audio, so this is two steps:
1. `transcribe`: local Whisper (faster-whisper on CPU) turns the audio into text.
2. `extract`: the OCR chat model, text only, returning the same shape as a
   handwritten-list scan so the SÚKL lookup and merge can be reused.
"""

import io
import os
import threading

import av
import numpy as np
import requests
from faster_whisper import WhisperModel
from ocr import package
from ocr.auto import HandwrittenMedication
from pydantic import BaseModel, Field

# tiny/base are fast but poor at Czech; small is the smallest usable one, medium is
# noticeably better but ~3x slower on CPU.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
# Empty = auto-detect, which is unreliable on short clips, hence Czech by default.
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "cs") or None
WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR") or None

# Biases recognition towards drug names and dosing phrases.
TRANSCRIBE_HINT = (
    "Seznam léků a jejich dávkování. Prestarium Neo 5 mg jedna ráno, Godasal 100 mg "
    "jedna večer, Euthyrox 50 mikrogramů, Devenal dvakrát denně, Warfarin ob den."
)

PROMPT = (
    "Below is a transcript of someone dictating the medications they take, usually in "
    "Czech. It comes from speech recognition, so medication names may be misspelled, "
    "split into several words or written phonetically.\n"
    "Extract EVERY medication mentioned, one entry per medication, in the order they "
    "are mentioned. Do not merge different medications and do not invent entries. "
    "Ignore filler words; if the speaker corrects themselves, use the corrected version. "
    "If no medication is mentioned, return an empty list. For each medication extract:\n"
    "- name: the medication name, fixed to the most likely real product or substance "
    "name if the transcript mangled it, including the strength if said, with numbers "
    'as digits (e.g. "Prestarium Neo 5 mg").\n'
    "- usage: when it is taken, normalized to one of three notations:\n"
    '  1. "a-b-c": pieces in the morning, at noon and in the evening (night counts as '
    'evening), e.g. "jednu ráno a jednu večer" -> "1-0-1", "půl ráno" -> "1/2-0-0".\n'
    '  2. "á n dní" / "á n dny": one piece every n days, e.g. "ob den" -> "á 2 dny", '
    '"jednou týdně" -> "á 7 dní".\n'
    '  3. "k*": k times a day with no set time, e.g. "třikrát denně" -> "3*".\n'
    '  If the timing is not said or fits none of these, use "". Do not guess.\n'
    'Respond with ONLY valid JSON, no commentary: {"medications":[{"name":"string","usage":"string"}]}\n\n'
    "Transcript:\n"
)


class DictationResult(BaseModel):
    medications: list[HandwrittenMedication] = Field(default_factory=list)


_model: WhisperModel | None = None
_lock = threading.Lock()


def _whisper() -> WhisperModel:
    """Loaded on first use (a few seconds); kept for the life of the process."""
    global _model
    with _lock:
        if _model is None:
            _model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
                download_root=WHISPER_MODEL_DIR,
            )
        return _model


def _decode(audio: bytes) -> np.ndarray:
    """Any format ffmpeg can decode (webm, m4a, mp3, wav, ogg, ...) -> 16 kHz mono float32.

    Done here rather than by faster-whisper, whose own decoder passes an `av.open()`
    argument that current PyAV no longer accepts.
    """
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    chunks = []
    with av.open(io.BytesIO(audio)) as container:
        for frame in container.decode(audio=0):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=None).astype(np.float32) / 32768.0


def transcribe(audio: bytes) -> str:
    segments, _ = _whisper().transcribe(
        _decode(audio),
        language=WHISPER_LANGUAGE,
        initial_prompt=TRANSCRIBE_HINT,
        beam_size=5,
        # Skips silence, which also stops Whisper hallucinating text into it.
        vad_filter=True,
    )
    # `segments` is lazy: decoding happens while iterating.
    return " ".join(segment.text.strip() for segment in segments).strip()


def extract(transcript: str) -> list[HandwrittenMedication]:
    resp = requests.post(
        f"{package.BASE_URL}/chat/completions",
        headers={"Content-Type": "application/json", "api-key": package.API_KEY},
        json={
            "model": package.resolve_model(),
            "stream": False,
            "temperature": 1,
            "max_completion_tokens": 1500,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": PROMPT + transcript}],
        },
        timeout=180,
    )
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    text = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content")
    if not text:
        raise RuntimeError("No response text received from the model.")

    return DictationResult.model_validate(package.extract_json(text)).medications
