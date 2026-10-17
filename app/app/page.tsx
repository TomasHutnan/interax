import { Button } from "@/components/ui/button";
import { ClipboardPlus, UserRound } from "lucide-react";
import Link from "next/link";

export default function Page() {
    return <div className={"min-h-dvh grid place-items-center"}>
        <div className={"flex flex-col gap-4 min-w-64"}>
            <div>
                <h1 className={"text-center text-4xl font-bold tracking-tight"}>InteraX</h1>
                <p className={"text-center"}>Please select the view (MVP).</p>
            </div>
            <div className={"space-y-1"}>
                <Link href={"/doctor"}><Button className={"w-full"}><ClipboardPlus/>Doctor</Button></Link>
                <Link href={"/patient"}><Button className={"w-full"}><UserRound/>Patient</Button></Link>
            </div>
        </div>
    </div>
}
