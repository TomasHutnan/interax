import { Dispatch, SetStateAction, useState } from "react";
import {
  MPatientForm,
  MPrescription,
  PatientForm,
  Prescription,
} from "@/lib/typings";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "../ui/button";
import { cn } from "cn";
import { toast } from "../ui/toast";
import { getErrorMessage } from "@/lib/hooks/use-swr-fetch";
import { fetchSubstances } from "@/lib/substances";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { useTranslations } from "next-intl";

export default function PrescriptionTable({
  pres,
  setState,
  highlight,
}: {
  pres: MPrescription[];
  setState: Dispatch<SetStateAction<MPatientForm>>;
  highlight: number[];
}) {
  const t = useTranslations("doctor.prescriptions");
  const update = (index: number, change: (p: MPrescription) => MPrescription) =>
    setState((prev) => ({
      ...prev,
      prescriptions: prev.prescriptions.map((p, i) =>
        i === index ? change(p) : p,
      ),
    }));

  const add = () =>
    setState((prev) => ({
      ...prev,
      prescriptions: [
        ...prev.prescriptions,
        { drug: "", subs: "", mg: "", usage: "" },
      ],
    }));

  const [filling, setFilling] = useState<number[]>([]);

  const fill = (index: number, name: string) => {
    if (filling.includes(index)) return;

    setFilling((prev) => [...prev, index]);
    fetchSubstances(name)
      .then((res) =>
        setState((prev) => ({
          ...prev,
          // skip if the row was removed or renamed in the meantime
          prescriptions: prev.prescriptions.map((p, i) =>
            i !== index || p.drug.trim() !== name
              ? p
              : {
                  ...p,
                  drug: p.drug || res.drug,
                  subs: p.subs || res.subs.join(" / "),
                  usage: p.usage || res.usage,
                },
          ),
        })),
      )
      .catch((err) =>
        toast.add({
          type: "error",
          title: getErrorMessage(
            err instanceof Error ? err : new Error(String(err)),
            { 404: t("notFound") },
          ),
        }),
      )
      .finally(() => setFilling((prev) => prev.filter((i) => i !== index)));
  };

  const remove = (index: number) =>
    setState((prev) => ({
      ...prev,
      prescriptions: prev.prescriptions.filter((_, i) => i !== index),
    }));

  return (
    <div className="border border-muted-foreground surface shadow-md p-4 space-y-2">
      <div className={"flex gap-x-2 justify-between items-center"}>
        <div className={"flex gap-x-2 items-center"}>
          <p className="font-bold">{t("title")}</p>
        </div>
        <div className={"flex gap-x-2 items-center"}>
          <Button
            type={"button"}
            variant={"outline"}
            aria-label={t("add")}
            onClick={add}
          >
            <Plus />
            {t("add")}
          </Button>
        </div>
      </div>
      {pres.length > 0 && (
        <Table>
          <TableBody>
            {pres.map((p, i) => (
              <TableRow
                key={i}
                className={cn(
                  highlight.includes(i) && "bg-primary/20 hover:bg-primary/20",
                )}
              >
                <TableCell>
                  <CellInput
                    placeholder={t("drugPlaceholder")}
                    value={p.drug}
                    onChange={(drug) => update(i, (cur) => ({ ...cur, drug }))}
                  />
                </TableCell>
                <TableCell className={"w-px"}>{t("withDosing")}</TableCell>
                <TableCell>
                  <CellInput
                    placeholder="0-0-0 / á"
                    value={p.usage}
                    onChange={(usage) =>
                      update(i, (cur) => ({ ...cur, usage }))
                    }
                  />
                </TableCell>
                <TableCell className={"w-px"}>{t("of")}</TableCell>
                <TableCell>
                  <div className={"flex gap-x-2 items-center"}>
                    <CellInput
                      placeholder={t("substancesPlaceholder")}
                      value={p.subs}
                      onChange={(names) =>
                        update(i, (cur) => ({ ...cur, subs: names }))
                      }
                    />
                    {p.drug.trim() && !p.subs.trim() && (
                      <Button
                        type={"button"}
                        variant={"outline"}
                        className={"shrink-0"}
                        disabled={filling.includes(i)}
                        onClick={() => fill(i, p.drug.trim())}
                      >
                        {filling.includes(i) ? t("filling") : t("autoFill")}
                      </Button>
                    )}
                  </div>
                </TableCell>
                <TableCell className={"w-px"}>
                  <Button
                    type={"button"}
                    variant={"destructive"}
                    size={"icon-xs"}
                    aria-label={t("delete")}
                    onClick={() => remove(i)}
                  >
                    <Trash2 />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function CellInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <input
      placeholder={placeholder}
      type={"text"}
      className={
        "w-full rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      }
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
