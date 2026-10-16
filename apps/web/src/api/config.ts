/**
 * Runtime configuration derived from Vite environment variables.
 * Only public values belong here; secrets must never reach the bundle.
 */

const raw = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Base URL of the PHANTOM API (no trailing slash). */
export const API_BASE_URL = raw.replace(/\/+$/, "");

/** WebSocket URL for the live transport, derived from the API base. */
export function wsUrl(): string {
  const base = API_BASE_URL.replace(/^http/, "ws");
  return `${base}/ws`;
}

/** True when no explicit API base was configured (using the local default). */
export const USING_DEFAULT_API_BASE = !import.meta.env.VITE_API_BASE_URL;
