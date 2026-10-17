import { XIcon } from "lucide-react";
import { Button } from "../ui/button";
import { Dispatch, SetStateAction, useEffect, useMemo, useState } from "react";
import { Interaction, MPatientForm } from "@/lib/typings";
import { useGetInteractions } from "@/lib/hooks/bundles";
import { Spinner } from "../ui/spinner";
import { Badge } from "../ui/badge";
import { useTranslations } from "next-intl";
import {
  interactionInputs,
  meetsThreshold,
  normalizeSeverity,
  rowOf,
  Severity,
  SEVERITIES,
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
  const t = useTranslations("interactions");
  const inputs = useMemo(() => interactionInputs(state), [state]);

  return (
    <div className="sticky top-16 self-start shrink-0 w-[300px] max-h-[75dvh] flex flex-col gap-2 border border-muted-foreground surface shadow-md p-4">
      <div className={"flex shrink-0 gap-x-2 justify-between items-center"}>
        <p className="font-bold">{t("panel.title")}</p>
        <div className={"flex gap-x-2 items-center"}>
          <Button
            type={"button"}
            variant={"outline"}
            aria-label={t("panel.closeLabel")}
            onClick={() => setOpen(false)}
          >
            <XIcon />
            {t("panel.close")}
          </Button>
        </div>
      </div>
      <SeveritySlider threshold={threshold} setThreshold={setThreshold} />
      {!inputs.complete ? (
        <p className="text-center">{t("panel.incomplete")}</p>
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
  const t = useTranslations("interactions");
  return (
    <label className="block shrink-0 space-y-1 pb-2 border-b border-border">
      <span className="flex justify-between text-sm">
        <span>{t("slider.label")}</span>
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
        aria-valuetext={t(`severity.${threshold}`)}
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
  const t = useTranslations("interactions");
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
        {t("panel.checking")}
      </div>
    );

  if (data.length === 0)
    return <p className="text-center">{t("panel.none")}</p>;

  const shown = data.filter((int) => meetsThreshold(int, threshold));
  const hidden = data.length - shown.length;

  return (
    <>
      {/* only the list scrolls; header, slider and the hidden-count footer stay put */}
      <div className="-mx-4 min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 [scrollbar-gutter:stable] [scrollbar-width:thin]">
        {shown.length === 0 && (
          <p className="text-center">{t("panel.noneAtThreshold")}</p>
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
      </div>
      {hidden > 0 && (
        <p className="shrink-0 border-t border-border pt-2 text-center text-sm text-muted-foreground">
          {t("panel.hidden", { count: hidden })}
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
  const t = useTranslations("interactions");
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
          {t.rich("panel.pair", {
            first,
            second,
            u: (chunks) => <span className="underline">{chunks}</span>,
          })}
        </span>
      </p>
      <p>{int[2] || t("panel.noExplanation")}</p>
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
  return <IntBadge0 severity={severity} />;
}

export function IntBadge0({ severity }: { severity: Severity }) {
  const t = useTranslations("interactions");
  const badge = BADGES[severity];
  return (
    <Badge variant={badge.variant} className={badge.className}>
      {t(`severity.${severity}`)}
    </Badge>
  );
}
