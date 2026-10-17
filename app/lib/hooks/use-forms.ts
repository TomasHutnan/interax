import { useMemo, useSyncExternalStore } from "react";
import { parseForms, parseUploads, readRawForms, readRawUploads, StoredForms, StoredUploads, subscribeForms } from "@/lib/storage";

/**
 * Returns the patient forms persisted in the local storage, or `undefined` until they can be read (server render and hydration).
 */
export function useForms(): StoredForms | undefined {
    const raw = useSyncExternalStore<string | null | undefined>(subscribeForms, readRawForms, () => undefined);
    return useMemo(() => raw === undefined ? undefined : parseForms(raw), [raw]);
}

/**
 * Returns the uploads persisted in the local storage, or `undefined` until they can be read (server render and hydration).
 */
export function useUploads(): StoredUploads | undefined {
    const raw = useSyncExternalStore<string | null | undefined>(subscribeForms, readRawUploads, () => undefined);
    return useMemo(() => raw === undefined ? undefined : parseUploads(raw), [raw]);
}
