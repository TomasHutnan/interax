"use client";
import { useTranslations } from "next-intl";
import { Check, X } from "lucide-react";
import { useShareConsent } from "@/lib/hooks/use-forms";
import { saveShareConsent } from "@/lib/storage";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../ui/dialog";
import { toast } from "../ui/toast";

/**
 * Asks once, on the patient's first visit, whether they agree to share anonymous data.
 * The answer is kept on this device and sent along with every code they create.
 */
export default function ShareConsentDialog() {
  const t = useTranslations("patient.consent");
  const consent = useShareConsent();

  function answer(share: boolean) {
    if (!saveShareConsent(share))
      toast.add({ type: "error", title: t("saveFailed") });
  }

  return (
    // Not dismissable: an explicit answer is required (closing would ask again anyway).
    <Dialog open={consent === null} disablePointerDismissal>
      <DialogContent>
        <div className={"space-y-2"}>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription className={"text-base"}>
            {t("description")}
          </DialogDescription>
          <p className={"text-sm text-muted-foreground"}>{t("changeLater")}</p>
        </div>
        <DialogFooter>
          <Button
            type={"button"}
            variant={"outline"}
            size={"lg"}
            onClick={() => answer(false)}
          >
            <X />
            {t("no")}
          </Button>
          <Button type={"button"} size={"lg"} onClick={() => answer(true)}>
            <Check />
            {t("yes")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** One-line status with a toggle, for the forms list. */
export function ShareConsentToggle() {
  const t = useTranslations("patient.consent");
  const consent = useShareConsent();
  if (consent == null) return null;

  return (
    <p className={"flex flex-wrap items-center gap-x-2 text-muted-foreground"}>
      {consent ? t("statusOn") : t("statusOff")}
      <button
        type={"button"}
        className={"cursor-pointer font-medium text-foreground underline"}
        onClick={() => saveShareConsent(!consent)}
      >
        {consent ? t("turnOff") : t("turnOn")}
      </button>
    </p>
  );
}
