import type { User } from "@/components/contexts/auth";
import { PatientForm } from "@/lib/typings";

const FORMS_KEY = "interax.patient-forms";
const UPLOADS_KEY = "interax.patient-uploads";
const USER_KEY = "interax.doctor-user";
const EVENT = "interax-patient-storage";

/**
 * Patient forms keyed by their creation timestamp (as a string).
 */
export type StoredForms = Record<string, PatientForm>;

/**
 * An upload of a form, as returned by the server.
 */
export type Upload = {
    id: string,
    uploaded_at: string
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

function parseRecord<T>(raw: string | null, valid: (value: T) => boolean): Record<string, T> {
    if (!raw) return {};

    try {
        const parsed = JSON.parse(raw);
        const result: Record<string, T> = {};
        for (const [id, value] of Object.entries(parsed ?? {})) {
            if (/^\d+$/.test(id) && valid(value as T))
                result[id] = value as T;
        }
        return result;
    } catch {
        return {};
    }
}

export const readRawForms = () => readRaw(FORMS_KEY);
export const readRawUploads = () => readRaw(UPLOADS_KEY);
export const readRawUser = () => readRaw(USER_KEY);

export function parseForms(raw: string | null): StoredForms {
    return parseRecord<PatientForm>(raw, f => Array.isArray(f?.prescriptions) && !!f?.treatment && typeof f.treatment === "object");
}

export function parseUploads(raw: string | null): StoredUploads {
    return parseRecord<Upload>(raw, u => typeof u?.id === "string" && typeof u?.uploaded_at === "string" && !Number.isNaN(Date.parse(u.uploaded_at)));
}

export function parseUser(raw: string | null): User | null {
    if (!raw) return null;

    try {
        const user = JSON.parse(raw);
        return typeof user?.username === "string" && typeof user?.password === "string" ? { username: user.username, password: user.password } : null;
    } catch {
        return null;
    }
}

/**
 * Persists the user, or forgets it if `null`.
 */
export function saveUser(user: User | null): boolean {
    if (!user) {
        try {
            localStorage.removeItem(USER_KEY);
        } catch {
            return false;
        }
        window.dispatchEvent(new Event(EVENT));
        return true;
    }

    return writeRaw(USER_KEY, user);
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
    return writeRaw(UPLOADS_KEY, { ...parseUploads(readRawUploads()), [id]: upload });
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
