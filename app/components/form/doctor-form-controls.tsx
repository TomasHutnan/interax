import { MPatientForm } from "@/lib/typings";
import { Button } from "../ui/button";
import { Check, Clipboard, Eye, EyeClosed, RotateCcw } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Dispatch, SetStateAction, useCallback } from "react";
import { toast } from "../ui/toast";

export default function DoctorFormControls({
  reset,
  state,
  open,
  setOpen,
  onFinish,
}: {
  reset: () => void;
  state: MPatientForm;
  open: boolean;
  setOpen: Dispatch<SetStateAction<boolean>>;
  onFinish: () => void;
}) {
  return (
    <div className="w-full flex gap-2 justify-between">
      <div className="flex gap-2">
        <CopyButton state={state} />
        <Button onClick={() => setOpen((prev) => !prev)}>
          {!open ? <Eye /> : <EyeClosed />}
          {!open ? "See interactions" : "Hide interactions"}
        </Button>
      </div>
      <div className="flex gap-2">
        <Button onClick={reset}>
          <RotateCcw />
          Reset
        </Button>
        <Button onClick={onFinish}>
          <Check />
          Finish viewing
        </Button>
      </div>
    </div>
  );
}

function CopyButton({ state }: { state: MPatientForm }) {
  const copy = useCallback(
    (style: string, fn: (f: MPatientForm) => string) => {
      toast.promise(navigator.clipboard.writeText(fn(state)), {
        loading: "Copying...",
        success: `Copied to clipboard (${style})`,
        error: (e: Error) => `This did not work out (${e.message})`,
      });
    },
    [state],
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button />}>
        <Clipboard />
        Copy as text
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuGroup className={"space-y-0"}>
          <DropdownMenuItem className={"p-0 m-0"}>
            <Button
              variant={"ghost"}
              onClick={() => copy("verbose", formatVerbose)}
            >
              Verbose (multiline)
            </Button>
          </DropdownMenuItem>
          <DropdownMenuItem className={"p-0 m-0"}>
            <Button
              variant={"ghost"}
              onClick={() => copy("compact", formatCompact)}
            >
              Compact (oneline)
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
