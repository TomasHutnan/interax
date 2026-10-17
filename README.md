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
- **[`database/`](./database):** Postgres image with the drug vocabularies loaded from CSV.
- **[`deploy/`](./deploy):** Azure Container Apps deployment script.
- **[`experiments/`](./experiments):** Research and prototyping workspace for OCR models, prompts, and evaluation datasets.

## Running locally

```sh
docker compose up -d --build
docker compose exec server python -m app.manage create-user <name> --role clinician
```

The app is on <http://localhost:3000> (patients at `/patient`, clinicians at `/doctor`). The
browser only talks to the Next.js app, which proxies `/api/*` to the server, so the session
cookie is first-party. The API docs are on <http://localhost:8080/docs>.

## Deploying to Azure

```fish
fish deploy/azure.fish
```

Creates/updates three Container Apps: `interax` (the public web app), `interax-server`
(internal only) and `interax-db` (internal only). See the script header for the `.env`
settings it reads. The public URL is `https://interax.<environment-domain>`.

### A nicer URL

The `<random>.swedencentral.azurecontainerapps.io` part comes from the Container Apps
environment and can't be changed; only the first label (the app name, `interax`) can.
For a real name you need a domain (~10 €/year, e.g. from Cloudflare or Porkbun; Azure
doesn't sell domains through this subscription). Container Apps then serves it with a free,
auto-renewing managed certificate:

```fish
set FQDN (az containerapp show -n interax -g rg-team89 --query properties.configuration.ingress.fqdn -o tsv)
az containerapp show -n interax -g rg-team89 --query properties.customDomainVerificationId -o tsv
# At the DNS provider, for app.example.com:
#   CNAME  app          -> $FQDN
#   TXT    asuid.app    -> <the verification id above>
az containerapp hostname add  -n interax -g rg-team89 --hostname app.example.com
az containerapp hostname bind -n interax -g rg-team89 --hostname app.example.com \
    --environment aca-team89-sandbox --validation-method CNAME
```

For an apex domain (`example.com`), use an A record to the environment's static IP and
`--validation-method HTTP` instead. The hackathon sandbox may forbid custom domains or
managed certificates by policy; if `hostname bind` is denied, that's why. Free subdomain
services (DuckDNS, etc.) usually can't host the `asuid` TXT record, so they don't work here.
