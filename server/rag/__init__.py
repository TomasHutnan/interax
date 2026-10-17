"""Self-contained InterSystems IRIS RAG, APIM LLM Adjudication & FHIR R4 module."""

from rag.pipeline import RagInteraction, check_rag_interactions

__all__ = ["RagInteraction", "check_rag_interactions"]
