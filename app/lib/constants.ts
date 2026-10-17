export const API_URL = process.env.NEXT_PUBLIC_API_URL || "<undefined>";

/**
 * How long an uploaded form (and its code) stays valid, counted from the upload timestamp.
 */
export const UPLOAD_TTL_MS = 30 * 60 * 1000;
