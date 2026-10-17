import { useMemo, useSyncExternalStore } from "react";
import {
  parseForms,
  parseShareConsent,
  parseUploads,
  readRawForms,
  readRawShareConsent,
  readRawUploads,
  StoredForms,
  StoredUploads,
  subscribeForms,
} from "@/lib/storage";

/**
 * Returns the patient forms persisted in the local storage, or `undefined` until they can be read (server render and hydration).
 */
export function useForms(): StoredForms | undefined {
  const raw = useSyncExternalStore<string | null | undefined>(
    subscribeForms,
    readRawForms,
    () => undefined,
  );
  return useMemo(
    () => (raw === undefined ? undefined : parseForms(raw)),
    [raw],
  );
}

/**
 * Returns the uploads persisted in the local storage, or `undefined` until they can be read (server render and hydration).
 */
export function useUploads(): StoredUploads | undefined {
  const raw = useSyncExternalStore<string | null | undefined>(
    subscribeForms,
    readRawUploads,
    () => undefined,
  );
  return useMemo(
    () => (raw === undefined ? undefined : parseUploads(raw)),
    [raw],
  );
}

/**
 * Returns whether the patient agreed to share anonymous data: `null` if not asked yet,
 * `undefined` until the local storage can be read (server render and hydration).
 */
export function useShareConsent(): boolean | null | undefined {
  const raw = useSyncExternalStore<string | null | undefined>(
    subscribeForms,
    readRawShareConsent,
    () => undefined,
  );
  return raw === undefined ? undefined : parseShareConsent(raw);
}
