# InterSystems IRIS Clinical RAG & FHIR R4 Pipeline (`experiments/rag-interactions/`)

End-to-end implementation of the 5-stage InterSystems IRIS pharmacological normalization, deterministic DDI screening, native vector semantic retrieval (`VECTOR_DOT_PRODUCT`), Azure APIM LLM adjudication, and HL7 FHIR R4 persistence pipeline.

## Live InterSystems IRIS Tables (`USER` namespace at `172.160.70.239:1972`)

- **`ClinicalData.SuklRegistry`** (`69,848` rows): 7-digit SÚKL DLP codes, brand names, English INN active substances, Czech substance names, strengths, forms, and WHO ATC codes/names.
- **`ClinicalData.Interactions`** (`29,681` rows): Major/Critical drug-drug interactions from DDInter (`code_A.csv` – `code_V.csv`) enriched with CYP450/DPYD/SLCO1B1/TPMT metabolic mechanism text.
- **`ClinicalKnowledge.CpicVectors`** (`1,110` rows): 384-dimensional embeddings (`sentence-transformers/all-MiniLM-L6-v2`) over CPIC PDF guidelines (`publication.pdf`, `supplement.pdf`) and flattened Excel recommendation/CDS alert tables (`VECTOR(DOUBLE, 384)`).
- **FHIR R4 Repository**: Enabled and live at `http://172.160.70.239:52773/csp/healthshare/fhir/r4`.

## Files

- [`config.py`](file:///home/tomas/dev/rakathon/interax/experiments/rag-interactions/config.py) — IRIS, FHIR R4, Azure APIM (`gpt-6-1-sol-dz-eu`), and local dataset paths.
- [`01_preprocess_and_ingest.py`](file:///home/tomas/dev/rakathon/interax/experiments/rag-interactions/01_preprocess_and_ingest.py) — Parses SÚKL, WHO ATC, DDInter, and CPIC Excel/PDF files; generates 384-d embeddings; bulk loads into IRIS.
- [`02_iris_schema_and_verify.py`](file:///home/tomas/dev/rakathon/interax/experiments/rag-interactions/02_iris_schema_and_verify.py) — Creates/verifies IRIS SQL schemas and indexes and probes the FHIR R4 endpoint.
- [`03_pipeline.py`](file:///home/tomas/dev/rakathon/interax/experiments/rag-interactions/03_pipeline.py) — Core `ClinicalIRISPipeline` class implementing the 5 phases (SÚKL normalization, DDInter lookup, `VECTOR_DOT_PRODUCT` Top-3 retrieval, APIM JSON adjudication, and FHIR R4 `MedicationStatement` + `DetectedIssue` creation).
- [`04_demo_verify.py`](file:///home/tomas/dev/rakathon/interax/experiments/rag-interactions/04_demo_verify.py) — Runs severe oncology conflict test cases (**Tamoxifen + Paroxetine** and **Capecitabine + Brivudine**) and verifies live persistence via `GET /csp/healthshare/fhir/r4/DetectedIssue?severity=high`.

## Usage

```bash
# Run the end-to-end verification and FHIR R4 demo
uv run python 04_demo_verify.py

# Re-run full data ingestion into IRIS (only needed if resetting tables)
uv run python 01_preprocess_and_ingest.py
```
