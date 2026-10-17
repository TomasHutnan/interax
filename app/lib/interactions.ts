import { Interaction, MPatientForm, Prescription } from "./typings";
import { baseFetcher, HttpError } from "./hooks/use-swr-fetch";

export type Severity = Interaction[3];

/**
 * Lowest to highest. `unknown` is lowest so the minimum threshold shows everything.
 */
export const SEVERITIES: Severity[] = [
  "unknown",
  "minor",
  "moderate",
  "major",
  "contraindicated",
];

export function normalizeSeverity(s: string): Severity {
  return (SEVERITIES as string[]).includes(s) ? (s as Severity) : "unknown";
}

export function meetsThreshold(int: Interaction, threshold: Severity): boolean {
  return (
    SEVERITIES.indexOf(normalizeSeverity(int[3])) >=
    SEVERITIES.indexOf(threshold)
  );
}

const splitSubs = (s: string) => s.split(/[/,]/).map((e) => e.trim());

/**
 * What the interactions endpoint is asked about: every substance of every row, flattened.
 * `offsets[i]` is how many substances row `i` contributed (prescriptions first, then treatment),
 * which maps an interaction's substance index back to its row.
 */
export function interactionInputs(state: MPatientForm) {
  const rows = [
    ...state.prescriptions.map((p) => p.subs),
    ...state.treatment.subs.map((s) => s.name),
  ];
  const complete = rows.every((r) => r.trim());
  const split = rows.map(splitSubs);
  const substances = split.flat();
  return {
    complete,
    substances,
    offsets: split.map((s) => s.length),
    key: JSON.stringify(substances),
  };
}

/**
 * Row index (prescriptions first, then treatment) of the substance at `i`, or -1.
 */
export function rowOf(i: number, offsets: number[]): number {
  let start = 0;
  for (let b = 0; b < offsets.length; b++) {
    start += offsets[b];
    if (i < start) return b;
  }
  return -1;
}

export type RepoInteraction = [string, string, string, Severity];

export type RepoPayload = {
  meds: Prescription[];
  interactions: RepoInteraction[];
};

export function toRepoPayload(
  state: MPatientForm,
  substances: string[],
  interactions: Interaction[],
): RepoPayload {
  const meds: Prescription[] = [
    ...state.prescriptions.map((p) => ({
      drug: p.drug.trim(),
      mg: "",
      subs: splitSubs(p.subs).filter(Boolean),
      usage: p.usage.trim(),
    })),
    ...state.treatment.subs.map((s) => ({
      drug: s.name.trim(),
      mg: "",
      subs: splitSubs(s.name).filter(Boolean),
      usage: s.dose.trim(),
    })),
  ]
    .map((m) => ({ ...m, drug: m.drug || m.subs[0] || "" }))
    .filter((m) => m.drug);

  const named: RepoInteraction[] = interactions
    .filter((int) => substances[int[0]] && substances[int[1]])
    .map((int) => [
      substances[int[0]],
      substances[int[1]],
      int[2] ?? "",
      normalizeSeverity(int[3]),
    ]);

  return { meds, interactions: named };
}

export async function uploadToRepo(payload: RepoPayload): Promise<void> {
  const res = await baseFetcher("/api/repo", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new HttpError(res.status, res.statusText);
}
