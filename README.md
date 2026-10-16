# InteraX

InteraX is an AI-powered medication digitization and drug interaction screening platform built for the **PillGaze** challenge at Rakathon.

## Challenge & Problem

Extracting accurate pharmacological anamnesis from messy, handwritten medication lists and pillbox photos is slow and error-prone. InteraX digitizes unstructured medication inputs into structured EHR-ready regimens, cross-references them against pharmacological databases for severe drug-drug interactions, and transfers structured data to clinicians anonymously.

### Key Capabilities
- **Multimodal Digitization:** OCR and visual parsing for pillbox packaging, handwritten dosage schedules, and oncological treatment regimens.
- **Drug-Drug Interaction Screening:** Automatic cross-referencing against pharmacological databases for contraindications and severe interactions.
- **Anonymous Data Handoff:** Time-limited, short PIN-based data transfer from patient to physician—no personally identifiable information (PII) stored or transmitted.
- **Clinician Dashboard:** Web interface to review, edit, and inspect patient medication tables and interaction alerts.

## Project Structure

- **[`app/`](./app):** Next.js / React frontend containing patient upload/PIN views and clinician dashboard.
- **[`server/`](./server):** Python backend (FastAPI) handling ingestion, parsing, interaction screening, and PIN sessions.
- **[`experiments/`](./experiments):** Research and prototyping workspace for OCR models, prompts, and evaluation datasets.
