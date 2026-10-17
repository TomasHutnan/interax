import useSWR, {BareFetcher, Key, SWRConfiguration} from "swr";
import useSWRImmutable from "swr/immutable";
import { API_URL } from "../constants";
import useSWRMutation from "swr/mutation";
import { useCallback } from "react";
import { toast } from "@/components/ui/toast";

export const ImmutableConfig = { revalidateIfStale: false, revalidateOnFocus: false, revalidateOnReconnect: false }

/**
 * HTTP error representation.
 */
export class HttpError extends Error {
    constructor(public readonly status: number, public readonly statusText: string) {
        super(`HTTP ${status} ${statusText}`);
        this.name = "HttpError";
    }
}

/**
 * Returns the message for this error, custom if `namespace` is defined and contains the respective messages, or the default.
 * The messages in the namespace should be keyed by `{code}` in case of HTTP errors and should contain a `general` message.
 * 
 * @param err the error to return a message for
 * @param messages custom messages to use, if any
 * @returns the error message
 */
export function getErrorMessage(err: Error, custom?: {[k: number]: string}): string {
    if (err instanceof HttpError) {
        if (custom && custom[err.status])
            return custom[err.status];
        
        switch (err.status) {
            case 400: return "Malformed request (E400).";
            case 401: return "You are not logged in (E401).";
            case 403: return "You do not have permission to do that (E403).";
            case 404: return "Not found (E404).";
            case 429: return "You are too fast. Try again. (E429).";
            case 500: return "Server error occurred. Try again. (E500)."
            case 503: return "No server available to service your request. Try again. (E503).";
            default: return `This did not work out (${err.message}).`
        }
    }

    return `This did not work out (${err.message})`;
}

function toURL(key: string) {
    return `${API_URL}${key}`;
}

export default function useSWRFetch<T>(key: Key, config?: SWRConfiguration<T, Error, BareFetcher<T>>) {
    return useSWR<T, Error>(key, fetcher, config)
}

export function useSWRImmutableFetch<T>(key: Key, config?: SWRConfiguration<T, Error, BareFetcher<T>>) {
    return useSWRImmutable<T, Error>(key, fetcher, config)
}

type MutateMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type MutationOptions<T, D> = {
    body?: boolean,
    toastMessages?: {
        loading: string,
        success: string,
        error: {[k: number]: string}
    },
    onMutation?: (arg: T, data: D) => Promise<void>
}

function createMutationFetcher<T, D>(key: (arg: T) => string, method: MutateMethod, body: boolean = true) {
    return async (url: string, { arg }: { arg: T }) => fetcher(key(arg), {
        method: method,
        body: !body || arg === undefined ? undefined : JSON.stringify(arg)
    }) as Promise<D>
}

export function useSWRMutationFetch<T, D>(mutKey: string, key: (arg: T) => string, method: MutateMethod, options: MutationOptions<T, D> = {}) {
    const mutation = useSWRMutation<D, unknown, string, T>(mutKey, createMutationFetcher<T, D>(key, method, options.body));
    const triggerMutation = mutation.trigger as (arg: T) => Promise<D>;

    const trigger = useCallback(async (arg: T) => {
        let promise = triggerMutation(arg).then(async data => {
            await options.onMutation?.(arg, data);
            return data;
        })

        if (options.toastMessages) {
            const msgs = options.toastMessages;
            promise = toast.promise(promise, {
                loading: msgs.loading,
                success: msgs.success,
                error: e => getErrorMessage(e, msgs.error)
            });
        }

        return promise;
    }, [triggerMutation, options]);

    return {
        ...mutation,
        trigger
    }
}

export const baseFetcher = (key: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    
    if (typeof init.body === "string" && !headers.has("Content-Type"))
        headers.set("Content-Type", "application/json");
    
    return fetch(toURL(key), {
        ...init,
        headers
    })
}

export const fetcher = (key: string, init?: RequestInit) => baseFetcher(key, init).then(async res => {
    if (!res.ok)
        throw new HttpError(res.status, res.statusText);
    
    return res.headers.get("Content-Type") === "application/json" ? res.json() : res.text();
});