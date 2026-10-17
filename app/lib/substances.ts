import { baseFetcher, HttpError } from "@/lib/hooks/use-swr-fetch";
import { parsePrescription } from "@/lib/scan";
import { Prescription } from "@/lib/typings";

/**
 * Looks the drug up, returning the prescription (with its substances) known for the name.
 * Fails with a 404 `HttpError` if the name does not resemble any drug.
 *
 * The name is sent as the `name` query parameter, since browsers cannot send a body with a GET request.
 */
export async function fetchSubstances(name: string): Promise<Prescription> {
    const res = await baseFetcher(`/medications/substances?name=${encodeURIComponent(name.trim())}`, { method: "GET" });
    if (!res.ok)
        throw new HttpError(res.status, res.statusText);

    return parsePrescription(await res.json());
}
