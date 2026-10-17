import { MPatientForm, MPrescription, PatientForm, Prescription, Treatment } from "@/lib/typings";
import PrescriptionTable from "./prescription-table";
import { useCallback, useMemo, useState } from "react";
import TreatmentTable from "./treatment-table";
import DoctorFormControls from "./doctor-form-controls";
import { toast } from "../ui/toast";
import InteractionsPanel from "./interactions-panel";

export default function DoctorForm({ form }: { form: PatientForm }) {
    const [state, setState] = useState<MPatientForm>(toMPatientForm(form));
    const [showInts, setShowInts] = useState(false);
    const [highlight, setHighlight] = useState<number[]>([]);
    const presCount = state.prescriptions.length;
    const presHighlight = useMemo(() => highlight.filter(i => i < presCount), [highlight, presCount]);
    const treatHighlight = useMemo(() => highlight.filter(i => i >= presCount).map(i => i - presCount), [highlight, presCount]);

    const reset = useCallback(() => {
        toast.add({
            type: "info",
            title: "Form reset."
        })
        setState(toMPatientForm(form))
    }, [form]);
    
    return <div className="flex gap-x-4">
        <div className="grow space-y-4">
            <PrescriptionTable pres={state.prescriptions} setState={setState} highlight={presHighlight} />
            <TreatmentTable treat={state.treatment} setState={setState} highlight={treatHighlight} />
            <DoctorFormControls reset={reset} state={state} open={showInts} setOpen={setShowInts} />
        </div>
        {showInts && <InteractionsPanel state={state} open={showInts} setOpen={setShowInts} setHighlight={setHighlight} />}
    </div>
}

function toMPatientForm(form: PatientForm): MPatientForm {
    return {
        prescriptions: form.prescriptions.map(toMPrescription),
        treatment: toMTreatment(form.treatment)
    }
}

function toMPrescription(pres: Prescription): MPrescription {
    return {
        drug: pres.drug + (pres.mg ? " " + pres.mg : ""),
        subs: pres.subs.join(" / "),
        usage: pres.usage
    }
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
    return treat
}