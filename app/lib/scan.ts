import { baseFetcher, HttpError } from "@/lib/hooks/use-swr-fetch";
import { tr } from "@/lib/i18n";
import { isEmptyPrescription } from "@/lib/prescriptions";
import { Prescription } from "@/lib/typings";

/**
 * Returns the mg value trimmed, ending in a mass unit ("mg" or "g") if it is not empty.
 */
export function normalizeMg(mg: string): string {
  const trimmed = mg.trim();
  if (!trimmed || /g$/i.test(trimmed)) return trimmed;

  return `${trimmed} mg`;
}

/**
 * Returns the prescriptions in the form expected by the scan endpoint (empty ones removed, trimmed fields, mg ending with a unit).
 */
export function prepareMeds(meds: Prescription[]): Prescription[] {
  return meds
    .filter((m) => !isEmptyPrescription(m))
    .map((m) => ({
      drug: m.drug.trim(),
      mg: normalizeMg(m.mg),
      subs: m.subs.map((s) => s.trim()),
      usage: m.usage.trim(),
    }));
}

export function parsePrescription(data: unknown): Prescription {
  const m = data as Partial<Record<keyof Prescription, unknown>> | null;
  return {
    drug: typeof m?.drug === "string" ? m.drug : "",
    mg: typeof m?.mg === "string" ? m.mg : "",
    subs: Array.isArray(m?.subs)
      ? m.subs.filter((s: unknown): s is string => typeof s === "string")
      : [],
    usage: typeof m?.usage === "string" ? m.usage : "",
  };
}

export function parseMeds(data: unknown): Prescription[] {
  const meds = (data as { meds?: unknown } | null)?.meds;
  if (!Array.isArray(meds)) throw new Error(tr("patient.scan.unexpected"));

  return meds.map(parsePrescription);
}

/**
 * Uploads the prescriptions and a file to the endpoint, returning the prescriptions recognized by the server.
 */
export async function postForMeds(
  path: string,
  meds: Prescription[],
  file: Blob,
  filename?: string,
): Promise<Prescription[]> {
  const body = new FormData();
  body.append("meds", JSON.stringify(prepareMeds(meds)));
  if (filename) body.append("file", file, filename);
  else body.append("file", file);

  const res = await baseFetcher(path, { method: "POST", body });
  if (!res.ok) throw new HttpError(res.status, res.statusText);

  return parseMeds(await res.json());
}

/**
 * Uploads the prescriptions and the scanned image, returning the prescriptions recognized by the server.
 */
export function scanMeds(
  meds: Prescription[],
  file: File,
): Promise<Prescription[]> {
  return postForMeds("/api/scan", meds, file);
}
