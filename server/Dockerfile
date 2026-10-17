FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/tmp/hf_cache

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --no-create-home app

# Bake the Whisper model into the image so the first dictation doesn't download it.
# Before `COPY . .` so code changes don't invalidate this (large) layer.
ARG WHISPER_MODEL=small
ENV WHISPER_MODEL=${WHISPER_MODEL} \
    WHISPER_MODEL_DIR=/models
RUN python -c "import os; from faster_whisper.utils import download_model; \
    download_model(os.environ['WHISPER_MODEL'], cache_dir=os.environ['WHISPER_MODEL_DIR'])" \
    && chown -R app /models

COPY . .

USER app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
