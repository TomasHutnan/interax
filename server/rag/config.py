"""Configuration, shared data models, and IRIS connection factory for the RAG pipeline."""

import os
from dataclasses import dataclass
from pathlib import Path

import iris
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if not ROOT_ENV_FILE.exists():
    ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)
load_dotenv(override=False)

IRIS_HOST = os.getenv("IRIS_HOST", "")
IRIS_PORT = int(os.getenv("IRIS_PORT", "1972"))
IRIS_HTTP_PORT = int(os.getenv("IRIS_HTTP_PORT", "52773"))
IRIS_NAMESPACE = os.getenv("IRIS_NAMESPACE", "USER")
IRIS_USER = os.getenv("IRIS_USER", "_SYSTEM")
IRIS_PASSWORD = os.getenv("IRIS_PASSWORD", "")

APIM_BASE_URL = os.getenv("UNSLOTH_BASE_URL", "").rstrip("/")
APIM_API_KEY = os.getenv("UNSLOTH_API_KEY", "")
APIM_MODEL = os.getenv("UNSLOTH_MODEL", "gpt-6-1-sol-dz-eu")

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class RagInteraction:
    substance_1: str
    substance_2: str
    pathophysiological_mechanism: str
    clinical_consequence: str
    severity: str


@dataclass
class ResolvedMed:
    input_text: str
    sukl_code: str
    brand_name: str
    active_substance: str
    canonical_name: str
    strength: str
    atc_code: str
    atc_name: str


class AdjudicatedPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pathophysiological_mechanism: str
    clinical_consequence: str


def get_iris_connection():
    """Open a DB-API connection to InterSystems IRIS."""
    return iris.connect(
        f"{IRIS_HOST}:{IRIS_PORT}/{IRIS_NAMESPACE}",
        IRIS_USER,
        IRIS_PASSWORD,
    )
