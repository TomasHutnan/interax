-- Whether the patient agreed to share anonymous data (medications and observed
-- interactions) with the FHIR repository. Chosen on their device, fixed per code.
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS share_data boolean NOT NULL DEFAULT false;
