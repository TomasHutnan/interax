import { useMemo, useState } from "react";
import { cn } from "cn";
import regimens from "@/lib/data/regimens.json";

const MAX_SUGGESTIONS = 100;

export default function RegimenInput({value, onChange, className}: {value: string, onChange: (value: string) => void, className?: string}) {
    const [open, setOpen] = useState(false);
    const [active, setActive] = useState(-1);

    const suggestions = useMemo(() => {
        const query = value.trim().toLowerCase();
        if (!query)
            return [];

        const starts: string[] = [];
        const contains: string[] = [];
        for (const name of regimens as string[]) {
            const lower = name.toLowerCase();
            if (lower.startsWith(query))
                starts.push(name);
            else if (lower.includes(query))
                contains.push(name);
        }
        return [...starts, ...contains].slice(0, MAX_SUGGESTIONS);
    }, [value]);

    const visible = open && suggestions.length > 0 && !(suggestions.length === 1 && suggestions[0] === value);

    const select = (name: string) => {
        onChange(name);
        setOpen(false);
        setActive(-1);
    };

    return <div className={"relative"}>
        <input
            type={"text"}
            className={cn("w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}
            value={value}
            onChange={e => {
                onChange(e.target.value);
                setOpen(true);
                setActive(-1);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onKeyDown={e => {
                if (!visible)
                    return;
                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive(a => Math.min(a + 1, suggestions.length - 1));
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive(a => Math.max(a - 1, 0));
                } else if (e.key === "Enter" && active >= 0) {
                    e.preventDefault();
                    select(suggestions[active]);
                } else if (e.key === "Escape") {
                    setOpen(false);
                }
            }}/>
        {visible && <ul
            role={"listbox"}
            className={"absolute z-10 mt-1 max-h-60 w-full min-w-48 overflow-y-auto rounded-md border bg-popover text-popover-foreground shadow-md"}>
            {suggestions.map((name, i) =>
                <li
                    key={name}
                    role={"option"}
                    aria-selected={i === active}
                    ref={el => { if (i === active) el?.scrollIntoView({block: "nearest"}); }}
                    className={cn("cursor-pointer px-2 py-1 text-sm", i === active ? "bg-accent text-accent-foreground" : "hover:bg-accent/50")}
                    onMouseDown={e => {
                        e.preventDefault();
                        select(name);
                    }}>
                    {name}
                </li>
            )}
        </ul>}
    </div>
}
