"use client";
import DoctorView from "@/components/form/doctor-view";
import { Suspense } from "react";

export default function Page() {
    return <Suspense>
        <DoctorView/>
    </Suspense>
}