"use client";
import { ReactNode, useCallback, useMemo, useState, useSyncExternalStore } from "react";
import { AuthContext, User } from "@/components/contexts/auth";
import Menu from "@/components/menu/menu";
import { parseUser, readRawUser, saveUser, subscribeForms } from "@/lib/storage";

export default function DoctorShell({ children }: { children: ReactNode }) {
    // undefined until the local storage can be read (server render and hydration)
    const raw = useSyncExternalStore<string | null | undefined>(subscribeForms, readRawUser, () => undefined);
    // used only if the local storage is not writable (e.g. blocked), so that logging in still works for this session
    const [fallback, setFallback] = useState<User | null>(null);
    const stored = useMemo(() => raw === undefined ? null : parseUser(raw), [raw]);

    const setUser = useCallback((user: User | null) => setFallback(saveUser(user) ? null : user), []);

    return <AuthContext.Provider value={{user: stored ?? fallback, loaded: raw !== undefined, setUser}}>
        <Menu />
        <main className={"min-h-dvh flex flex-col text-sm py-16 px-8 md:px-32"}>
            {children}
        </main>
    </AuthContext.Provider>
}
