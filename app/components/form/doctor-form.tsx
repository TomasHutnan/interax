import {
  MPatientForm,
  MPrescription,
  PatientForm,
  Prescription,
  Treatment,
  Interaction,
} from "@/lib/typings";
import PrescriptionTable from "./prescription-table";
import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import TreatmentTable from "./treatment-table";
import DoctorFormControls from "./doctor-form-controls";
import { toast } from "../ui/toast";
import InteractionsPanel from "./interactions-panel";
import FinishDialog from "./finish-dialog";
import { Severity } from "@/lib/interactions";

export default function DoctorForm({ form }: { form: PatientForm }) {
  const t = useTranslations("doctor.form");
  const router = useRouter();
  const [state, setState] = useState<MPatientForm>(toMPatientForm(form));
  const [showInts, setShowInts] = useState(false);
  const [highlight, setHighlight] = useState<number[]>([]);
  const [threshold, setThreshold] = useState<Severity>("minor");
  const [knownInts, setKnownInts] = useState<{
    key: string;
    data: Interaction[];
  } | null>(null);
  const [finishing, setFinishing] = useState(false);
  const presCount = state.prescriptions.length;
  const presHighlight = useMemo(
    () => highlight.filter((i) => i < presCount),
    [highlight, presCount],
  );
  const treatHighlight = useMemo(
    () => highlight.filter((i) => i >= presCount).map((i) => i - presCount),
    [highlight, presCount],
  );

  const onIntsLoaded = useCallback(
    (key: string, data: Interaction[]) => setKnownInts({ key, data }),
    [],
  );

  const exit = useCallback(() => {
    setFinishing(false);
    router.replace("/doctor/code");
    toast.add({
      type: "info",
      title: t("sessionClosed"),
    });
  }, [router, t]);

  const reset = useCallback(() => {
    toast.add({
      type: "info",
      title: t("reset"),
    });
    setState(toMPatientForm(form));
  }, [form, t]);

  return (
    <div className="flex gap-x-4">
      <div className="grow space-y-4">
        <PrescriptionTable
          pres={state.prescriptions}
          setState={setState}
          highlight={presHighlight}
        />
        <TreatmentTable
          treat={state.treatment}
          setState={setState}
          highlight={treatHighlight}
        />
        <DoctorFormControls
          reset={reset}
          state={state}
          open={showInts}
          setOpen={setShowInts}
          onFinish={exit}
          onFinishAndSend={() => setFinishing(true)}
        />
      </div>
      {showInts && (
        <InteractionsPanel
          state={state}
          open={showInts}
          setOpen={setShowInts}
          setHighlight={setHighlight}
          threshold={threshold}
          setThreshold={setThreshold}
          onLoaded={onIntsLoaded}
        />
      )}
      <FinishDialog
        open={finishing}
        onOpenChange={setFinishing}
        state={state}
        threshold={threshold}
        known={knownInts}
        onExit={exit}
      />
    </div>
  );
}

function toMPatientForm(form: PatientForm): MPatientForm {
  return {
    prescriptions: form.prescriptions.map(toMPrescription),
    treatment: toMTreatment(form.treatment),
  };
}

function toMPrescription(pres: Prescription): MPrescription {
  return {
    drug: pres.drug + (pres.mg ? " " + pres.mg : ""),
    subs: pres.subs.join(" / "),
    usage: pres.usage,
  };
}

// function toMUsage(usage: Usage): string {
//     if (usage.type === "DAILY")
//         return `${usage.pcs}x`
//     if (usage.type === "TIMED")
//         return `${usage.pcs.join("-")}`
//     if (usage.type === "PERIODIC")
//         return `á ${usage.every}`
//     return "-"
// }

function toMTreatment(treat: Treatment): Treatment {
  return treat;
}
