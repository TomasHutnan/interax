import useSWR, { BareFetcher, Key, SWRConfiguration } from "swr";
import useSWRImmutable from "swr/immutable";
import useSWRMutation from "swr/mutation";
import { useCallback } from "react";
import { toast } from "@/components/ui/toast";

export const ImmutableConfig = {
  revalidateIfStale: false,
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
};

/**
 * Dispatched on `window` when a request outside `/api/auth/` gets a 401, i.e. the session ended (expired, logged out elsewhere).
 */
export const UNAUTHORIZED_EVENT = "interax-unauthorized";

/**
 * Sent with every request. The server requires it on state-changing requests made with the session cookie (CSRF protection).
 */
const CSRF_HEADER = "X-Requested-With";

/**
 * HTTP error representation.
 */
export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
  ) {
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
export function getErrorMessage(
  err: Error,
  custom?: { [k: number]: string },
): string {
  if (err instanceof HttpError) {
    if (custom && custom[err.status]) return custom[err.status];

    switch (err.status) {
      case 400:
        return "Malformed request (E400).";
      case 401:
        return "You are not logged in (E401).";
      case 403:
        return "You do not have permission to do that (E403).";
      case 404:
        return "Not found (E404).";
      case 429:
        return "Too many requests. Wait a moment and try again (E429).";
      case 500:
        return "Server error occurred. Try again. (E500).";
      case 503:
        return "The service is temporarily unavailable. Try again shortly (E503).";
      default:
        return `This did not work out (${err.message}).`;
    }
  }

  return `This did not work out (${err.message})`;
}

export default function useSWRFetch<T>(
  key: Key,
  config?: SWRConfiguration<T, Error, BareFetcher<T>>,
) {
  return useSWR<T, Error>(key, fetcher, config);
}

export function useSWRImmutableFetch<T>(
  key: Key,
  config?: SWRConfiguration<T, Error, BareFetcher<T>>,
) {
  return useSWRImmutable<T, Error>(key, fetcher, config);
}

type MutateMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type MutationOptions<T, D> = {
  body?: boolean;
  toastMessages?: {
    loading: string;
    success: string;
    error: { [k: number]: string };
  };
  onMutation?: (arg: T, data: D) => Promise<void>;
};

function createMutationFetcher<T, D>(
  key: (arg: T) => string,
  method: MutateMethod,
  body: boolean = true,
) {
  return async (url: string, { arg }: { arg: T }) =>
    fetcher(key(arg), {
      method: method,
      body: !body || arg === undefined ? undefined : JSON.stringify(arg),
    }) as Promise<D>;
}

export function useSWRMutationFetch<T, D>(
  mutKey: string,
  key: (arg: T) => string,
  method: MutateMethod,
  options: MutationOptions<T, D> = {},
) {
  const mutation = useSWRMutation<D, unknown, string, T>(
    mutKey,
    createMutationFetcher<T, D>(key, method, options.body),
  );
  const triggerMutation = mutation.trigger as (arg: T) => Promise<D>;

  const trigger = useCallback(
    async (arg: T) => {
      let promise = triggerMutation(arg).then(async (data) => {
        await options.onMutation?.(arg, data);
        return data;
      });

      if (options.toastMessages) {
        const msgs = options.toastMessages;
        promise = toast.promise(promise, {
          loading: msgs.loading,
          success: msgs.success,
          error: (e) => getErrorMessage(e, msgs.error),
        });
      }

      return promise;
    },
    [triggerMutation, options],
  );

  return {
    ...mutation,
    trigger,
  };
}

/**
 * Fetches `key`, a same-origin path such as `/api/uploads` (the app proxies `/api/*` to the backend).
 */
export const baseFetcher = (key: string, init: RequestInit = {}) => {
  const headers = new Headers(init.headers);

  if (typeof init.body === "string" && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  headers.set(CSRF_HEADER, "interax");

  return fetch(key, {
    ...init,
    headers,
    credentials: "same-origin",
  }).then((res) => {
    if (res.status === 401 && !key.startsWith("/api/auth/"))
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    return res;
  });
};

export const fetcher = (key: string, init?: RequestInit) =>
  baseFetcher(key, init).then(async (res) => {
    if (!res.ok) throw new HttpError(res.status, res.statusText);

    return res.headers.get("Content-Type") === "application/json"
      ? res.json()
      : res.text();
  });
