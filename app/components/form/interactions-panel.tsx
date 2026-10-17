import { XIcon } from "lucide-react";
import { Button } from "../ui/button";
import { Dispatch, SetStateAction, useEffect, useMemo, useState } from "react";
import { Interaction, MPatientForm } from "@/lib/typings";
import { useGetInteractions } from "@/lib/hooks/bundles";
import { Spinner } from "../ui/spinner";
import { Badge } from "../ui/badge";
import {
  interactionInputs,
  meetsThreshold,
  normalizeSeverity,
  rowOf,
  Severity,
  SEVERITIES,
  SEVERITY_LABELS,
} from "@/lib/interactions";

type Props = {
  state: MPatientForm;
  open: boolean;
  setOpen: Dispatch<SetStateAction<boolean>>;
  setHighlight: Dispatch<SetStateAction<number[]>>;
  threshold: Severity;
  setThreshold: Dispatch<SetStateAction<Severity>>;
  /** Called with each loaded result, so it can be reused (e.g. when finishing the review). */
  onLoaded: (key: string, data: Interaction[]) => void;
};

export default function InteractionsPanel({
  state,
  setOpen,
  setHighlight,
  threshold,
  setThreshold,
  onLoaded,
}: Props) {
  const inputs = useMemo(() => interactionInputs(state), [state]);

  return (
    <div className="w-[300px] border border-muted-foreground shadow-md p-4 space-y-2">
      <div className={"flex gap-x-2 justify-between items-center"}>
        <p className="font-bold">Interactions:</p>
        <div className={"flex gap-x-2 items-center"}>
          <Button
            type={"button"}
            variant={"outline"}
            aria-label={"Close interactions"}
            onClick={() => setOpen(false)}
          >
            <XIcon />
            Close
          </Button>
        </div>
      </div>
      <SeveritySlider threshold={threshold} setThreshold={setThreshold} />
      {!inputs.complete ? (
        <p className="text-center">
          Fill in all substances to check interactions.
        </p>
      ) : (
        <Internal
          state={state}
          subsKey={inputs.key}
          offsets={inputs.offsets}
          threshold={threshold}
          setHighlight={setHighlight}
          onLoaded={onLoaded}
        />
      )}
    </div>
  );
}

export function SeveritySlider({
  threshold,
  setThreshold,
}: {
  threshold: Severity;
  setThreshold: Dispatch<SetStateAction<Severity>>;
}) {
  return (
    <label className="block space-y-1 pb-2 border-b border-border">
      <span className="flex justify-between text-sm">
        <span>Minimum severity:</span>
        <IntBadge0 severity={threshold} />
      </span>
      <input
        type="range"
        className="w-full accent-primary"
        min={0}
        max={SEVERITIES.length - 1}
        step={1}
        value={SEVERITIES.indexOf(threshold)}
        onChange={(e) =>
          setThreshold(SEVERITIES[Number(e.target.value)] ?? "unknown")
        }
        aria-valuetext={SEVERITY_LABELS[threshold]}
      />
    </label>
  );
}

function Internal({
  subsKey,
  offsets,
  state,
  threshold,
  setHighlight,
  onLoaded,
}: {
  state: MPatientForm;
  subsKey: string;
  offsets: number[];
  threshold: Severity;
  setHighlight: Dispatch<SetStateAction<number[]>>;
  onLoaded: Props["onLoaded"];
}) {
  const { trigger, isMutating, data } = useGetInteractions();

  // Keyed by the substance list itself, so editing e.g. a usage doesn't re-check.
  useEffect(() => {
    const substances = JSON.parse(subsKey) as string[];
    const timeout = setTimeout(
      () =>
        trigger({ substances })
          .then((d) => onLoaded(subsKey, d))
          .catch(() => {}),
      500,
    );
    return () => clearTimeout(timeout);
  }, [subsKey, trigger, onLoaded]);

  if (isMutating || !data)
    return (
      <div className="w-full flex flex-col items-center gap-2 pt-4 text-sm text-muted-foreground">
        <Spinner />
        Checking interactions...
      </div>
    );

  if (data.length === 0)
    return <p className="text-center">No interactions found.</p>;

  const shown = data.filter((int) => meetsThreshold(int, threshold));
  const hidden = data.length - shown.length;

  return (
    <>
      {shown.length === 0 && (
        <p className="text-center">
          No interactions at or above this severity.
        </p>
      )}
      {shown.map((e, i) => (
        <Int
          state={state}
          key={i}
          int={e}
          offsets={offsets}
          setHighlight={setHighlight}
        />
      ))}
      {hidden > 0 && (
        <p className="text-center text-sm text-muted-foreground">
          {hidden} less severe {hidden === 1 ? "interaction" : "interactions"}{" "}
          hidden.
        </p>
      )}
    </>
  );
}

function Int({
  state,
  offsets,
  int,
  setHighlight,
}: {
  state: MPatientForm;
  int: Interaction;
  offsets: number[];
  setHighlight: Dispatch<SetStateAction<number[]>>;
}) {
  const [hovered, setHovered] = useState(false);
  const offset = state.prescriptions.length;
  const fi = rowOf(int[0], offsets),
    si = rowOf(int[1], offsets);

  useEffect(() => {
    if (!hovered || fi < 0 || si < 0) return;
    setHighlight([fi, si]);
    return () => setHighlight([]);
  }, [hovered, fi, si, setHighlight]);

  if (fi < 0 || si < 0) return null;

  const first =
    fi < offset
      ? state.prescriptions[fi]?.drug
      : state.treatment.subs[fi - offset]?.name;
  const second =
    si < offset
      ? state.prescriptions[si]?.drug
      : state.treatment.subs[si - offset]?.name;

  if (!first || !second) return null;

  return (
    <div
      className="px-2 py-2 border-b border-border last:border-b-0 hover:bg-muted"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <p className="font-bold flex flex-wrap items-center gap-x-1">
        <IntBadge int={int} />
        <span>
          <span className="underline">{first}</span> and{" "}
          <span className="underline">{second}</span>
        </span>
      </p>
      <p>{int[2] || "No explanation available."}</p>
    </div>
  );
}

const BADGES: Record<
  Severity,
  { variant: "destructive" | "secondary" | "outline"; className?: string }
> = {
  contraindicated: { variant: "destructive" },
  major: {
    variant: "secondary",
    className: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  },
  moderate: {
    variant: "secondary",
    className: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  },
  minor: { variant: "secondary" },
  unknown: { variant: "outline" },
};

export function IntBadge({ int }: { int: Interaction }) {
  const severity = normalizeSeverity(int[3]);
    return <IntBadge0 severity={severity} />
}

export function IntBadge0({ severity }: { severity: Severity }) {
  const badge = BADGES[severity];
  return (
    <Badge variant={badge.variant} className={badge.className}>
      {SEVERITY_LABELS[severity]}
    </Badge>
  );
}