FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --no-create-home app

# Bake the Whisper and RAG embedding models into the image so the first
# dictation/interaction check doesn't download them. Before `COPY . .` so code
# changes don't invalidate this (large) layer. Downloaded as root, so the whole
# cache is handed to `app` afterwards (it runs as `app` and may write to it).
# Keep the embedding model name in sync with EMBEDDING_MODEL_NAME in rag/pipeline.py.
ARG WHISPER_MODEL=small
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV WHISPER_MODEL=${WHISPER_MODEL} \
    WHISPER_MODEL_DIR=/models \
    HF_HOME=/models/hf
RUN python -c "import os; from faster_whisper.utils import download_model; \
    download_model(os.environ['WHISPER_MODEL'], cache_dir=os.environ['WHISPER_MODEL_DIR'])" \
    && python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('${EMBEDDING_MODEL}')" \
    && chown -R app /models

COPY . .

USER app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
