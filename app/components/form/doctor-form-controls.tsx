import { MPatientForm } from "@/lib/typings";
import { Button } from "../ui/button";
import {
  Check,
  Clipboard,
  Eye,
  EyeClosed,
  RotateCcw,
  Send,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Dispatch, SetStateAction, useCallback } from "react";
import { toast } from "../ui/toast";
import { useTranslations } from "next-intl";

export default function DoctorFormControls({
  reset,
  state,
  open,
  setOpen,
  onFinish,
  onFinishAndSend,
}: {
  reset: () => void;
  state: MPatientForm;
  open: boolean;
  setOpen: Dispatch<SetStateAction<boolean>>;
  onFinish: () => void;
  /** Missing when the patient didn't agree to share data: then there's only "Finish". */
  onFinishAndSend?: () => void;
}) {
  const t = useTranslations("doctor.controls");
  return (
    <div className="w-full flex gap-2 justify-between">
      <div className="flex gap-2">
        <CopyButton state={state} />
        <Button onClick={() => setOpen((prev) => !prev)}>
          {!open ? <Eye /> : <EyeClosed />}
          {!open ? t("showInteractions") : t("hideInteractions")}
        </Button>
      </div>
      <div className="flex gap-2">
        <Button onClick={reset}>
          <RotateCcw />
          {t("reset")}
        </Button>
        {onFinishAndSend ? (
          <>
            <Button variant={"outline"} onClick={onFinish}>
              <Check />
              {t("finishWithoutSending")}
            </Button>
            <Button onClick={onFinishAndSend}>
              <Send />
              {t("finishAndSend")}
            </Button>
          </>
        ) : (
          <Button onClick={onFinish}>
            <Check />
            {t("finish")}
          </Button>
        )}
      </div>
    </div>
  );
}

function CopyButton({ state }: { state: MPatientForm }) {
  const t = useTranslations("doctor.controls.copy");
  const copy = useCallback(
    (style: "verbose" | "compact", fn: (f: MPatientForm) => string) => {
      toast.promise(navigator.clipboard.writeText(fn(state)), {
        loading: t("loading"),
        success: t("success", { style: t(`styles.${style}`) }),
        error: (e: Error) => t("error", { message: e.message }),
      });
    },
    [state, t],
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button />}>
        <Clipboard />
        {t("button")}
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuGroup className={"space-y-0"}>
          <DropdownMenuItem className={"p-0 m-0"}>
            <Button
              variant={"ghost"}
              onClick={() => copy("verbose", formatVerbose)}
            >
              {t("verbose")}
            </Button>
          </DropdownMenuItem>
          <DropdownMenuItem className={"p-0 m-0"}>
            <Button
              variant={"ghost"}
              onClick={() => copy("compact", formatCompact)}
            >
              {t("compact")}
            </Button>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function formatCompact(form: MPatientForm): string {
  return formatVerbose(form).split("\n").join(", ").replace(/\s+/g, " ");
}

function formatVerbose(form: MPatientForm): string {
  const e = [
    ...form.prescriptions.map((p) => [p.drug, p.usage]),
    ...form.treatment.subs.map((s) => [s.name, s.dose]),
  ].filter((e) => e[0].trim());
  const max = Math.max(...e.map((s) => s[0].trim().length)) + 3;

  return e.map((s) => formatSub(s, max)).join("\n");
}

function formatSub(s: string[], max: number) {
  const name = s[0].trim() + " ".repeat(max - s[0].trim().length);
  return `${name}${s[1].trim() || "???"}`;
}
