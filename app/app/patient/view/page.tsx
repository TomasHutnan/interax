import { Suspense } from "react";
import PatientView from "@/components/patient/patient-view";

export default function Page() {
    return <Suspense>
        <PatientView/>
    </Suspense>
}
