import { useEffect, useState } from "react";

/**
 * Returns the current time in milliseconds, refreshed every second while `active`.
 * Returns 0 until mounted (the time is unstable during prerendering).
 */
export function useNow(active: boolean): number {
    const [now, setNow] = useState(0);

    useEffect(() => {
        const timeout = setTimeout(() => setNow(Date.now()), 0);
        const interval = active ? setInterval(() => setNow(Date.now()), 1000) : undefined;
        return () => {
            clearTimeout(timeout);
            clearInterval(interval);
        };
    }, [active]);

    return now;
}
