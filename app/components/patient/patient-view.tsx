"use client";
import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForms } from "@/lib/hooks/use-forms";
import { PatientForm } from "@/lib/typings";
import { Spinner } from "../ui/spinner";
import PatientEditor from "./patient-editor";

export default function PatientView() {
    const params = useSearchParams();
    const router = useRouter();
    const forms = useForms();
    const id = params.get("id");
    const valid = id !== null && /^\d+$/.test(id);

    useEffect(() => {
        if (!valid) router.replace("/patient");
    }, [valid, router]);

    if (!valid || !forms)
        return <div className={"flex flex-1 items-center justify-center"}><Spinner className={"size-8"}/></div>

    return <PatientEditor key={id} id={id} initial={forms[id] ?? emptyForm()}/>
}

function emptyForm(): PatientForm {
    return {
        prescriptions: [{ drug: "", mg: "", subs: [], usage: "" }],
        treatment: { name: "", subs: [] }
    }
}
