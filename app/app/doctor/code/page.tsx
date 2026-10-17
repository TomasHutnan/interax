"use client";
import { useAuth } from "@/components/contexts/auth";
import { OTPForm } from "@/components/form/otp-form";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Page() {
    const auth = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (auth.loaded && !auth.user) router.replace("/doctor");
    }, [auth.loaded, auth.user, router]);
    
    if (!auth.loaded) return null;
    if (!auth.user) return <p>Not logged in.</p>;
    
    return <div className={"flex-1 grid place-items-center"}>
        <OTPForm/>
    </div>
}