import { PatientForm } from "@/lib/typings";

const FORMS_KEY = "interax.patient-forms";
const UPLOADS_KEY = "interax.patient-uploads";
/**
 * Where older versions kept the logged-in doctor, password included. Only read to delete it.
 */
const LEGACY_USER_KEY = "interax.doctor-user";
const EVENT = "interax-patient-storage";

/**
 * Patient forms keyed by their creation timestamp (as a string).
 */
export type StoredForms = Record<string, PatientForm>;

/**
 * An upload of a form, as returned by the server.
 * `expires_at` and `revoke_token` are missing for uploads stored by older versions.
 */
export type Upload = {
  id: string;
  uploaded_at: string;
  expires_at?: string;
  /**
   * Secret needed to revoke the code; only this device has it.
   */
  revoke_token?: string;
};

/**
 * Uploads keyed by the creation timestamp of the form they belong to.
 */
export type StoredUploads = Record<string, Upload>;

function readRaw(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    return false;
  }

  window.dispatchEvent(new Event(EVENT));
  return true;
}

function parseRecord<T>(
  raw: string | null,
  valid: (value: T) => boolean,
): Record<string, T> {
  if (!raw) return {};

  try {
    const parsed = JSON.parse(raw);
    const result: Record<string, T> = {};
    for (const [id, value] of Object.entries(parsed ?? {})) {
      if (/^\d+$/.test(id) && valid(value as T)) result[id] = value as T;
    }
    return result;
  } catch {
    return {};
  }
}

export const readRawForms = () => readRaw(FORMS_KEY);
export const readRawUploads = () => readRaw(UPLOADS_KEY);

export function parseForms(raw: string | null): StoredForms {
  return parseRecord<PatientForm>(
    raw,
    (f) =>
      Array.isArray(f?.prescriptions) &&
      !!f?.treatment &&
      typeof f.treatment === "object",
  );
}

export function parseUploads(raw: string | null): StoredUploads {
  return parseRecord<Upload>(
    raw,
    (u) =>
      typeof u?.id === "string" &&
      typeof u?.uploaded_at === "string" &&
      !Number.isNaN(Date.parse(u.uploaded_at)) &&
      (u.expires_at === undefined ||
        (typeof u.expires_at === "string" &&
          !Number.isNaN(Date.parse(u.expires_at)))) &&
      (u.revoke_token === undefined || typeof u.revoke_token === "string"),
  );
}

/**
 * Deletes the doctor (and their plaintext password) that older versions stored on this device.
 */
export function forgetLegacyUser(): void {
  try {
    localStorage.removeItem(LEGACY_USER_KEY);
  } catch {
    // storage not available, so nothing is stored either
  }
}

export function saveForm(id: string, form: PatientForm): boolean {
  return writeRaw(FORMS_KEY, { ...parseForms(readRawForms()), [id]: form });
}

export function deleteForm(id: string): boolean {
  const forms = parseForms(readRawForms());
  delete forms[id];
  return writeRaw(FORMS_KEY, forms);
}

export function saveUpload(id: string, upload: Upload): boolean {
  return writeRaw(UPLOADS_KEY, {
    ...parseUploads(readRawUploads()),
    [id]: upload,
  });
}

export function deleteUpload(id: string): boolean {
  const uploads = parseUploads(readRawUploads());
  delete uploads[id];
  return writeRaw(UPLOADS_KEY, uploads);
}

export function subscribeForms(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT, callback);
  };
}
