import { useForm } from "@/lib/hooks/bundles";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { HttpError } from "@/lib/hooks/use-swr-fetch";
import DoctorForm from "./doctor-form";
import { Spinner } from "../ui/spinner";
import { toast } from "../ui/toast";

export default function DoctorView() {
    const params = useSearchParams();
    const code = params.get("code");

    if (!code)
        return null;
    
    return <Internal code={code}/>
}

function Internal({code}: { code: string }) {
    const res = useForm(code);
    const router = useRouter();
    const notFound = res.error instanceof HttpError && res.error.status === 404;

    useEffect(() => {
        if (!notFound) return;
        toast.add({ type: "error", title: "No form found for this code." });
        router.replace("/doctor/code");
    }, [notFound, router]);

    if (notFound) return null;
    if (res.error) return <p>Error: {res.error.message}</p>;
    if (res.data === undefined) return <div className={"flex-1 grid place-items-center"}><Spinner className="size-8"/></div>;

    return <DoctorForm form={res.data.data}/>
}