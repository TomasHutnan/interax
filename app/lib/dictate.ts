import { postForMeds } from "@/lib/scan";
import { Prescription } from "@/lib/typings";

/**
 * Uploads the prescriptions and the recorded dictation (WAV), returning the prescriptions recognized by the server.
 */
export function dictateMeds(meds: Prescription[], wav: Blob): Promise<Prescription[]> {
    return postForMeds("/dictate", meds, wav, "dictation.wav");
}
