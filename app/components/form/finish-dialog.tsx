import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Send } from "lucide-react";
import { Interaction, MPatientForm } from "@/lib/typings";
import { useGetInteractions } from "@/lib/hooks/bundles";
import { getErrorMessage } from "@/lib/hooks/use-swr-fetch";
import {
  interactionInputs,
  meetsThreshold,
  Severity,
  toRepoPayload,
  uploadToRepo,
} from "@/lib/interactions";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../ui/dialog";
import { Spinner } from "../ui/spinner";
import { toast } from "../ui/toast";
import { IntBadge, IntBadge0 } from "./interactions-panel";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: MPatientForm;
  threshold: Severity;
  /** Last result from the interactions panel, reused if the substances haven't changed since. */
  known: { key: string; data: Interaction[] } | null;
  onExit: () => void;
};

/**
 * Shown when the doctor picks "Finish and send": lets them review which medications and observed
 * interactions (those at or above the severity threshold) go to the FHIR repository.
 */
export default function FinishDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {open && <Internal onCancel={() => onOpenChange(false)} {...rest} />}
      </DialogContent>
    </Dialog>
  );
}

function Internal({
  state,
  threshold,
  known,
  onExit,
  onCancel,
}: Omit<Props, "open" | "onOpenChange"> & { onCancel: () => void }) {
  const t = useTranslations("doctor.finish");
  const tInt = useTranslations("interactions");
  const inputs = useMemo(() => interactionInputs(state), [state]);
  const cached = known && known.key === inputs.key ? known.data : null;
  const { trigger, data: fetched, error } = useGetInteractions();
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (cached || !inputs.complete) return;
    trigger({ substances: inputs.substances }).catch(() => {});
  }, [cached, inputs, trigger]);

  const all = cached ?? fetched;
  const loading = inputs.complete && !all && !error;
  // Indices into `all`, so the checkboxes stay stable.
  const observed = useMemo(
    () =>
      (all ?? [])
        .map((int, i) => [int, i] as const)
        .filter(([int]) => meetsThreshold(int, threshold)),
    [all, threshold],
  );
  const selected = observed
    .filter(([, i]) => !excluded.has(i))
    .map(([int]) => int);
  const meds = toRepoPayload(state, inputs.substances, []).meds;

  function toggle(i: number) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (!next.delete(i)) next.add(i);
      return next;
    });
  }

  function send() {
    setSending(true);
    toast
      .promise(
        uploadToRepo(toRepoPayload(state, inputs.substances, selected)),
        {
          loading: t("toast.loading"),
          success: t("toast.success"),
          error: (err) =>
            getErrorMessage(
              err instanceof Error ? err : new Error(String(err)),
              {
                502: t("toast.rejected"),
                503: t("toast.notConfigured"),
              },
            ),
        },
      )
      .then(onExit)
      .catch(() => {})
      .finally(() => setSending(false));
  }

  return (
    <>
      <div className="space-y-1">
        <DialogTitle>{t("title")}</DialogTitle>
        <DialogDescription>
          {t("description", { count: meds.length })}
        </DialogDescription>
      </div>

      <div className="space-y-2">
        <p className="text-sm">
          {t.rich("atOrAbove", {
            badge: () => <IntBadge0 severity={threshold} />,
          })}
        </p>
        {!inputs.complete ? (
          <p className="text-sm text-muted-foreground">{t("incomplete")}</p>
        ) : loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            {t("checking")}
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{t("error")}</p>
        ) : observed.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("none")}</p>
        ) : (
          <ul className="max-h-64 overflow-y-auto border border-border">
            {observed.map(([int, i]) => (
              <li key={i} className="border-b border-border last:border-b-0">
                <label className="flex items-start gap-2 p-2 hover:bg-muted cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-1 accent-primary"
                    checked={!excluded.has(i)}
                    onChange={() => toggle(i)}
                    disabled={sending}
                  />
                  <span className="space-y-1">
                    <span className="flex flex-wrap items-center gap-1 font-bold">
                      <IntBadge int={int} />
                      {tInt("pair", {
                        first: inputs.substances[int[0]],
                        second: inputs.substances[int[1]],
                      })}
                    </span>
                    {int[2] && <span className="block text-sm">{int[2]}</span>}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={sending}>
          {t("back")}
        </Button>

        <Button
          onClick={send}
          disabled={sending || loading || meds.length === 0}
        >
          <Send />
          {sending ? t("sending") : t("confirm")}
        </Button>
      </DialogFooter>
    </>
  );
}
