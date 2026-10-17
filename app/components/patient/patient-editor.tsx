"use client";
import {
  ChangeEvent,
  KeyboardEvent,
  PointerEvent,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Camera, Check, Mic, Plus, Trash2, X } from "lucide-react";
import { PatientForm, Prescription } from "@/lib/typings";
import { saveForm } from "@/lib/storage";
import { scanMeds } from "@/lib/scan";
import { dictateMeds } from "@/lib/dictate";
import { useRecorder } from "@/lib/hooks/use-recorder";
import { getErrorMessage } from "@/lib/hooks/use-swr-fetch";
import { tr } from "@/lib/i18n";
import { phraseToast } from "@/lib/loading-phrases";
import { Button } from "../ui/button";
import { toast } from "../ui/toast";
import RegimenInput from "../form/regimen-input";

const MIN_DICTATION_MS = 500;

function micErrorMessage(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return tr("patient.editor.mic.denied");
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return tr("patient.editor.mic.notFound");
  return tr("patient.editor.mic.failed");
}

const INPUT_CLASS =
  "w-full rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export default function PatientEditor({
  id,
  initial,
}: {
  id: string;
  initial: PatientForm;
}) {
  const t = useTranslations("patient.editor");
  const router = useRouter();
  const [form, setForm] = useState<PatientForm>(initial);
  const [busy, setBusy] = useState(false);
  const recorder = useRecorder();
  const locked = busy || recorder.recording;
  const fileInput = useRef<HTMLInputElement>(null);

  const canSave =
    form.treatment.name.trim() !== "" ||
    form.prescriptions.some((p) => p.drug.trim() || p.usage.trim());

  const updatePrescription = (index: number, change: Partial<Prescription>) =>
    setForm((prev) => ({
      ...prev,
      prescriptions: prev.prescriptions.map((p, i) =>
        i === index ? { ...p, ...change } : p,
      ),
    }));

  const addPrescription = () =>
    setForm((prev) => ({
      ...prev,
      prescriptions: [
        ...prev.prescriptions,
        { drug: "", mg: "", subs: [], usage: "" },
      ],
    }));

  const removePrescription = (index: number) =>
    setForm((prev) => ({
      ...prev,
      prescriptions: prev.prescriptions.filter((_, i) => i !== index),
    }));

  function scan(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || busy) return;

    setBusy(true);
    try {
      phraseToast(scanMeds(form.prescriptions, file), {
        group: "photo",
        loading: t("toasts.readingPhoto"),
        success: t("toasts.scanned"),
        error: (err) =>
          getErrorMessage(err instanceof Error ? err : new Error(String(err))),
      })
        .then((prescriptions) =>
          setForm((prev) => ({ ...prev, prescriptions })),
        )
        .catch(() => {})
        .finally(() => setBusy(false));
    } catch {
      setBusy(false);
    }
  }

  function holdStart() {
    if (busy || recorder.recording) return;

    recorder
      .start()
      .catch((err) =>
        toast.add({ type: "error", title: micErrorMessage(err) }),
      );
  }

  function holdEnd() {
    recorder
      .stop()
      .then((result) => {
        if (!result) return;
        if (result.durationMs < MIN_DICTATION_MS) {
          toast.add({ type: "info", title: t("toasts.holdWhileSpeaking") });
          return;
        }

        setBusy(true);
        try {
          phraseToast(dictateMeds(form.prescriptions, result.wav), {
            group: "voice",
            loading: t("toasts.transcribing"),
            success: t("toasts.dictated"),
            error: (err) =>
              getErrorMessage(
                err instanceof Error ? err : new Error(String(err)),
              ),
          })
            .then((prescriptions) =>
              setForm((prev) => ({ ...prev, prescriptions })),
            )
            .catch(() => {})
            .finally(() => setBusy(false));
        } catch {
          setBusy(false);
        }
      })
      .catch(() => {});
  }

  function onHoldPointerDown(e: PointerEvent<HTMLElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    holdStart();
  }

  function onHoldKeyDown(e: KeyboardEvent<HTMLElement>) {
    if (e.key !== " " && e.key !== "Enter") return;
    e.preventDefault();
    if (!e.repeat) holdStart();
  }

  function onHoldKeyUp(e: KeyboardEvent<HTMLElement>) {
    if (e.key !== " " && e.key !== "Enter") return;
    e.preventDefault();
    holdEnd();
  }

  function save() {
    const cleaned: PatientForm = {
      prescriptions: form.prescriptions.filter(
        (p) => p.drug.trim() || p.usage.trim(),
      ),
      treatment: { name: form.treatment.name.trim(), subs: [] },
    };

    if (!saveForm(id, cleaned)) {
      toast.add({ type: "error", title: t("toasts.saveFailed") });
      return;
    }

    router.push("/patient");
    toast.add({ type: "success", title: t("toasts.saved") });
  }

  return (
    <div className={"space-y-4 border border-border surface p-4 shadow-md"}>
      <section className={"space-y-2"}>
        <div className={"flex flex-wrap items-center justify-between gap-2"}>
          <h2 className={"font-bold"}>{t("prescriptions")}</h2>
          <div className={"flex flex-wrap gap-2"}>
            <Button
              type={"button"}
              variant={"outline"}
              size={"lg"}
              disabled={locked}
              onClick={() => fileInput.current?.click()}
            >
              <Camera />
              {busy ? t("processing") : t("scan")}
            </Button>
            {recorder.supported && (
              <Button
                type={"button"}
                variant={recorder.recording ? "default" : "outline"}
                size={"lg"}
                className={"touch-none select-none"}
                disabled={busy}
                onPointerDown={onHoldPointerDown}
                onPointerUp={holdEnd}
                onPointerCancel={holdEnd}
                onLostPointerCapture={holdEnd}
                onKeyDown={onHoldKeyDown}
                onKeyUp={onHoldKeyUp}
                onBlur={holdEnd}
                onContextMenu={(e) => e.preventDefault()}
              >
                <Mic />
                {recorder.recording ? t("recording") : t("holdToSpeak")}
              </Button>
            )}
            <Button
              type={"button"}
              variant={"outline"}
              size={"lg"}
              disabled={locked}
              onClick={addPrescription}
            >
              <Plus />
              {t("addManually")}
            </Button>
          </div>
          <input
            ref={fileInput}
            type={"file"}
            accept={"image/png,image/jpeg"}
            className={"hidden"}
            onChange={scan}
          />
        </div>
        {form.prescriptions.length === 0 && (
          <p className={"py-4 text-center text-muted-foreground"}>
            {t("empty")}
          </p>
        )}
        <div className={"space-y-4"}>
          {form.prescriptions.map((p, i) => (
            <div
              key={i}
              className={
                "space-y-4 border border-muted-foreground p-4 shadow-md"
              }
            >
              <label className={"block space-y-2"}>
                <span className={"font-medium"}>{t("drug")}</span>
                <input
                  type={"text"}
                  className={INPUT_CLASS}
                  value={p.drug}
                  onChange={(e) =>
                    updatePrescription(i, { drug: e.target.value })
                  }
                />
              </label>
              <label className={"block space-y-2"}>
                <span className={"font-medium"}>{t("dosing")}</span>
                <input
                  type={"text"}
                  className={INPUT_CLASS}
                  placeholder={t("dosingPlaceholder")}
                  value={p.usage}
                  onChange={(e) =>
                    updatePrescription(i, { usage: e.target.value })
                  }
                />
              </label>
              <Button
                type={"button"}
                variant={"destructive"}
                size={"lg"}
                className={"w-full"}
                onClick={() => removePrescription(i)}
              >
                <Trash2 />
                {t("remove")}
              </Button>
            </div>
          ))}
        </div>
      </section>
      <section className={"space-y-2"}>
        <h2 className={"font-bold"}>{t("regimen")}</h2>
        <RegimenInput
          value={form.treatment.name}
          onChange={(name) =>
            setForm((prev) => ({ ...prev, treatment: { name, subs: [] } }))
          }
        />
      </section>
      <div className={"flex gap-2"}>
        <Button
          type={"button"}
          variant={"outline"}
          size={"lg"}
          onClick={() => router.push("/patient")}
        >
          <X />
          {t("cancel")}
        </Button>
        <Button
          type={"button"}
          size={"lg"}
          disabled={!canSave || locked}
          onClick={save}
        >
          <Check />
          {t("save")}
        </Button>
      </div>
    </div>
  );
}
