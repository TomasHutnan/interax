import { Prescription } from "@/lib/typings";

/**
 * Whether all fields of the prescription are empty (blank strings or no/blank substances).
 */
export function isEmptyPrescription(p: Prescription): boolean {
    return !(p.drug ?? "").trim() && !(p.mg ?? "").trim() && !(p.usage ?? "").trim() && (p.subs ?? []).every(s => !(s ?? "").trim());
}
