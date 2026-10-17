import { UPLOAD_TTL_MS } from "@/lib/constants";
import { baseFetcher, HttpError } from "@/lib/hooks/use-swr-fetch";
import { isEmptyPrescription } from "@/lib/prescriptions";
import { Upload } from "@/lib/storage";
import { PatientForm } from "@/lib/typings";

/**
 * Returns the time (ms) the upload expires at.
 */
export function expiresAt(upload: Upload): number {
  return upload.expires_at
    ? Date.parse(upload.expires_at)
    : Date.parse(upload.uploaded_at) + UPLOAD_TTL_MS;
}

/**
 * Returns the time (ms) left until the upload expires, never more than the full lifetime and never less than 0.
 */
export function remainingMs(upload: Upload, now: number): number {
  const lifetime = expiresAt(upload) - Date.parse(upload.uploaded_at);
  return Math.min(lifetime, Math.max(0, expiresAt(upload) - now));
}

export function isActive(
  upload: Upload | undefined,
  now: number,
): upload is Upload {
  return !!upload && remainingMs(upload, now) > 0;
}

/**
 * Formats the remaining time as `m:ss` (or `h:mm:ss`).
 */
export function formatRemaining(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const h = Math.floor(total / 3600),
    m = Math.floor((total % 3600) / 60),
    s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

function prepareForm(form: PatientForm): PatientForm {
  return {
    prescriptions: form.prescriptions
      .filter((p) => !isEmptyPrescription(p))
      .map((p) => ({
        drug: (p.drug ?? "").trim(),
        mg: (p.mg ?? "").trim(),
        subs: (p.subs ?? []).map((s) => (s ?? "").trim()),
        usage: (p.usage ?? "").trim(),
      })),
    treatment: {
      name: (form.treatment.name ?? "").trim(),
      subs: [],
    },
  };
}

/**
 * Uploads the form, returning the upload (code, timestamps and revoke token) assigned by the server.
 */
export async function uploadForm(form: PatientForm): Promise<Upload> {
  const res = await baseFetcher("/api/uploads", {
    method: "POST",
    body: JSON.stringify(prepareForm(form)),
  });
  if (!res.ok) throw new HttpError(res.status, res.statusText);

  const data = await res.json();
  const isDate = (v: unknown): v is string =>
    typeof v === "string" && !Number.isNaN(Date.parse(v));
  if (
    typeof data?.id !== "string" ||
    !data.id ||
    !isDate(data?.uploaded_at) ||
    !isDate(data?.expires_at) ||
    typeof data?.revoke_token !== "string"
  )
    throw new Error("Unexpected response from the server");

  return {
    id: data.id,
    uploaded_at: data.uploaded_at,
    expires_at: data.expires_at,
    revoke_token: data.revoke_token,
  };
}

/**
 * Revokes the code. A code the server no longer knows (404) counts as revoked.
 */
export async function revokeUpload(upload: Upload): Promise<void> {
  const headers: HeadersInit = upload.revoke_token
    ? { "X-Revoke-Token": upload.revoke_token }
    : {};
  const res = await baseFetcher(
    `/api/uploads/${encodeURIComponent(upload.id)}`,
    { method: "DELETE", headers },
  );
  if (!res.ok && res.status !== 404)
    throw new HttpError(res.status, res.statusText);
}
