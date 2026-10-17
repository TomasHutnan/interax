import { useCallback, useEffect } from "react";
import useSWR from "swr";
import { parseUser, User } from "@/components/contexts/auth";
import { baseFetcher, HttpError, UNAUTHORIZED_EVENT } from "@/lib/hooks/use-swr-fetch";

const ME_KEY = "/api/auth/me";

async function fetchMe(): Promise<User | null> {
    const res = await baseFetcher(ME_KEY);
    if (res.status === 401)
        return null;
    if (!res.ok)
        throw new HttpError(res.status, res.statusText);

    return parseUser(await res.json());
}

/**
 * The server-side session of the clinician, as known to the server (`/api/auth/me`).
 * Becomes logged out when any request reports the session as gone (401).
 */
export function useSession() {
    const { data, error, mutate } = useSWR<User | null, Error>(ME_KEY, fetchMe, { shouldRetryOnError: false });

    const setUser = useCallback((user: User | null) => {
        mutate(user, { revalidate: false });
    }, [mutate]);

    useEffect(() => {
        const onUnauthorized = () => setUser(null);
        window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
        return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    }, [setUser]);

    return {
        user: data ?? null,
        loaded: data !== undefined || error !== undefined,
        setUser
    };
}
