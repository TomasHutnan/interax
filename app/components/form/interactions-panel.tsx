import { XIcon } from "lucide-react";
import { Button } from "../ui/button";
import { Dispatch, SetStateAction, useEffect, useMemo, useState } from "react";
import { Interaction, MPatientForm } from "@/lib/typings";
import { useGetInteractions } from "@/lib/hooks/bundles";
import { Spinner } from "../ui/spinner";
import { Badge } from "../ui/badge";

export default function InteractionsPanel({ state, open, setOpen, setHighlight }: { state: MPatientForm, open: boolean, setOpen: Dispatch<SetStateAction<boolean>>, setHighlight: Dispatch<SetStateAction<number[]>> }) {
    const complete = useMemo(() => state.prescriptions.every(p => p.subs.trim()) && state.treatment.subs.every(s => s.name.trim()), [state]);
    const substances = useMemo(() => [...state.prescriptions.map(p => p.subs).join("/").split(/[/,]/), ...state.treatment.subs.map(s => s.name).join("/").split(/[/,]/)].map(e => e.trim()), [state]);
    const offsets = useMemo(() => [...state.prescriptions.map(p => p.subs.split(/[/,]/).length), ...state.treatment.subs.map(p => p.name.split(/[/,]/).length)], [state]);
    
    return <div className="w-[300px] border border-muted-foreground shadow-md p-4 space-y-2">
        <div className={"flex gap-x-2 justify-between items-center"}>
            <p className="font-bold">Interactions:</p>
            <div className={"flex gap-x-2 items-center"}>
                <Button type={"button"} variant={"outline"} aria-label={"Add prescription"} onClick={() => setOpen(false)}>
                    <XIcon/>Close
                </Button>
            </div>
        </div>
        {!complete ? <p className="text-center">Cannot show interactions unless all substances are filled in.</p> : <Internal state={state} subs={substances} offsets={offsets} setHighlight={setHighlight}/>}
    </div>
}

function Internal({subs, offsets, state, setHighlight}: {state: MPatientForm, subs: string[], offsets: number[], setHighlight: Dispatch<SetStateAction<number[]>>}) {
    const { trigger, isMutating, data } = useGetInteractions();

    useEffect(() => {
        const timeout = setTimeout(() => trigger({substances: subs}).catch(() => { }), 500);
        return () => clearTimeout(timeout);
    }, [subs, trigger]);

    if (isMutating || !data)
        return <div className="w-full flex justify-center pt-4"><Spinner/></div>

    if (data.length === 0)
        return <p className="text-center">No interactions found.</p>
    
    return <>
        {data.map((e, i) => <Int state={state} key={i} int={e} offsets={offsets} setHighlight={setHighlight} />)}
    </>
}

function Int({ state, offsets, int, setHighlight }: { state: MPatientForm, int: Interaction, offsets: number[], setHighlight: Dispatch<SetStateAction<number[]>> }) {
    const [hovered, setHovered] = useState(false);
    const offset = state.prescriptions.length;
    const fi = findIndex(int[0], offsets), si = findIndex(int[1], offsets);

    useEffect(() => {
        if (!hovered || fi < 0 || si < 0)
            return;
        setHighlight([fi, si]);
        return () => setHighlight([]);
    }, [hovered, fi, si, setHighlight]);

    if (fi < 0 || si < 0) return null;
    
    const first = fi < offset ? state.prescriptions[fi]?.drug : state.treatment.subs[fi - offset]?.name;
    const second = si < offset ? state.prescriptions[si]?.drug : state.treatment.subs[si - offset]?.name;

    if (!first || !second) return null;
    
    return <div className="px-2 py-2 border-b border-border last:border-b-0 hover:bg-muted" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
        <p className="font-bold flex flex-wrap items-center gap-x-1"><IntBadge int={int}/><span><span className="underline">{first}</span> and <span className="underline">{second}</span></span></p>
        <p>{int[2] || "No provable reason to display."}</p>
    </div>
}

function findIndex(i: number, offsets: number[]): number {
    let start = 0;
    for (let b = 0; b < offsets.length; b++) {
        start += offsets[b];
        if (i < start)
            return b;
    }
    return -1;
}

const BADGES: Record<Interaction[3], { label: string, variant: "destructive" | "secondary" | "outline", className?: string }> = {
    contraindicated: { label: "Contraindicated", variant: "destructive" },
    major: { label: "Major", variant: "secondary", className: "bg-orange-500/15 text-orange-700 dark:text-orange-400" },
    moderate: { label: "Moderate", variant: "secondary", className: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400" },
    minor: { label: "Minor", variant: "secondary" },
    unknown: { label: "Unknown", variant: "outline" },
}

function IntBadge({ int }: { int: Interaction }) {
    const badge = BADGES[int[3]] ?? BADGES.unknown;
    return <Badge variant={badge.variant} className={badge.className}>{badge.label}</Badge>
}
