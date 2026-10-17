import { Dispatch, SetStateAction, useMemo } from "react";
import { MPatientForm, Treatment, TreatmentSub } from "@/lib/typings";
import { DatabaseBackup, Plus, Trash2 } from "lucide-react";
import { Button } from "../ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { cn } from "cn";
import RegimenInput from "./regimen-input";
import regimens from "@/lib/data/regimens.json";
import { useGetComponents } from "@/lib/hooks/bundles";

export default function TreatmentTable({ treat, setState, highlight }: { treat: Treatment, setState: Dispatch<SetStateAction<MPatientForm>>, highlight: number[] }) {
    const {trigger, isMutating} = useGetComponents();
    
    const update = (change: (t: Treatment) => Treatment) =>
        setState(prev => ({...prev, treatment: change(prev.treatment)}));

    const updateSub = (index: number, change: (s: TreatmentSub) => TreatmentSub) =>
        update(cur => ({
            ...cur,
            subs: cur.subs.map((s, i) => i === index ? change(s) : s)
        }));

    const add = () => update(cur => ({...cur, subs: [...cur.subs, {name: "", dose: ""}]}));

    const remove = (index: number) => update(cur => ({ ...cur, subs: cur.subs.filter((_, i) => i !== index) }));

    const syncComponents = () => {
        trigger(treat.name).then(res => update(cur => ({ ...cur, subs: res.map(s => ({ name: s, dose: "" })) }))).catch(() => { })
    }

    const syncable = useMemo(() => regimens.includes(treat.name), [treat.name]);

    return <div className="border border-muted-foreground shadow-md p-4 space-y-2">
        <div className={"flex gap-x-2 justify-between items-center"}>
            <div className="flex gap-x-2 items-center">
                <p className="font-bold">Regimen: </p>
                <RegimenInput
                    value={treat.name || ""}
                    onChange={name => update(cur => ({ ...cur, name }))} />
            </div>
            <div className="flex gap-x-2 items-center">
                <Button type={"button"} variant={"outline"} aria-label={"Apply components"} onClick={syncComponents} disabled={!syncable}>
                    <DatabaseBackup/>Apply components
                </Button>
                <Button type={"button"} variant={"outline"} aria-label={"Add substance"} onClick={add}>
                    <Plus/>Add component
                </Button>
            </div>
        </div>
        {treat.subs.length > 0 && <Table>
            <TableBody>
                {treat.subs.map((s, i) =>
                    <TableRow key={i} className={cn(highlight.includes(i) && "bg-primary/20 hover:bg-primary/20")}>
                        <TableCell>
                            <CellInput placeholder="Substance 50mg"
                                value={s.name}
                                onChange={name => updateSub(i, cur => ({ ...cur, name }))} />
                        </TableCell>
                        <TableCell className={"w-px"}>
                            with dosing
                        </TableCell>
                        <TableCell>
                            <CellInput placeholder="0-0-0 / á"
                                value={s.dose}
                                onChange={dose => updateSub(i, cur => ({ ...cur, dose }))} />
                        </TableCell>
                        <TableCell className={"w-px"}>
                            <Button type={"button"} variant={"destructive"} size={"icon-xs"} aria-label={"Delete substance"} onClick={() => remove(i)}>
                                <Trash2 />
                            </Button>
                        </TableCell>
                    </TableRow>
                )}
            </TableBody>
        </Table>}
    </div>
}

function CellInput({value, onChange, className, placeholder}: {value: string, onChange: (value: string) => void, className?: string, placeholder?: string}) {
    return <input
        placeholder={placeholder}
        type={"text"}
        className={cn("placeholder:text-muted-foreground/50 w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}
        value={value}
        onChange={e => onChange(e.target.value)}/>
}
