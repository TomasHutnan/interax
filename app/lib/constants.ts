/**
 * How long an uploaded form (and its code) stays valid, counted from the upload timestamp.
 * Only a fallback for uploads stored before the server started returning `expires_at`.
 */
export const UPLOAD_TTL_MS = 60 * 60 * 1000;
