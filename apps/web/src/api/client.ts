/**
 * Typed PHANTOM API client.
 *
 * Every method returns a typed value or throws an {@link ApiError}. Loading,
 * empty, offline, unauthorized, and server-error states are represented
 * distinctly via {@link ApiError.category} so callers can render the right
 * recovery UI.
 */

import { API_BASE_URL } from "./config";
import type {
  AnalyticsSummary,
  AuditEntry,
  EvidenceStatusSummary,
  HealthResponse,
  IncidentEvent,
  ObservationFrame,
  Paginated,
  PipelineInfo,
  PipelinePreflight,
  RegionModel,
  RuleConfig,
  RuleDefinition,
  RuleType,
  RuleVersionEntry,
  RunSummary,
  Severity,
  SystemStatus,
} from "./types";

export type ApiErrorCategory =
  | "offline"
  | "timeout"
  | "unauthorized"
  | "not_found"
  | "validation"
  | "conflict"
  | "server"
  | "unknown";

export class ApiError extends Error {
  readonly status: number;
  readonly category: ApiErrorCategory;
  readonly code: string;
  readonly detail: string;
  readonly correlationId: string | null;

  constructor(
    message: string,
    opts: {
      status?: number;
      category?: ApiErrorCategory;
      code?: string;
      detail?: string;
      correlationId?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status ?? 0;
    this.category = opts.category ?? "unknown";
    this.code = opts.code ?? "unknown";
    this.detail = opts.detail ?? "";
    this.correlationId = opts.correlationId ?? null;
  }
}

function categorize(status: number): ApiErrorCategory {
  if (status === 401 || status === 403) return "unauthorized";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  timeoutMs?: number;
}

function buildQuery(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal, timeoutMs = 15000 } = options;
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onAbort, { once: true });
  }
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${buildQuery(query)}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      // Distinguish caller cancellation from timeout.
      if (signal?.aborted) {
        throw new ApiError("Request cancelled.", { category: "unknown", code: "cancelled" });
      }
      throw new ApiError("The API did not respond in time.", {
        category: "timeout",
        code: "timeout",
      });
    }
    throw new ApiError("Cannot reach the PHANTOM API.", {
      category: "offline",
      code: "offline",
    });
  } finally {
    window.clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onAbort);
  }

  if (!response.ok) {
    let detail = "";
    let code = `http_${response.status}`;
    let message = `Request failed with status ${response.status}.`;
    try {
      const data = (await response.json()) as {
        detail?: unknown;
        error?: string;
        code?: string;
      };
      if (typeof data.detail === "string") {
        detail = data.detail;
        message = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        const first = data.detail[0] as { msg?: string; loc?: unknown[] };
        detail = first?.msg ?? "";
        message = `Validation error: ${detail}`;
      } else if (data.error) {
        message = data.error;
      }
      if (data.code) code = data.code;
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(message, {
      status: response.status,
      category: categorize(response.status),
      code,
      detail,
    });
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Health and system
// -------------------------------------------------------------------------
export const api = {
  health: () => request<HealthResponse>("/health"),

  systemStatus: () => request<SystemStatus>("/api/v1/system/status"),

  systemConfig: () =>
    request<{ config: Record<string, unknown> }>("/api/v1/system/config"),

  // -- Runs --------------------------------------------------------------
  listRuns: (limit = 50) =>
    request<{ items: RunSummary[] }>("/api/v1/runs", { query: { limit } }),

  getRun: (runId: string) => request<RunSummary>(`/api/v1/runs/${runId}`),

  activeRun: () =>
    request<{ active_run_id: string | null; pipeline: PipelineInfo }>("/api/v1/runs/active"),

  startRun: (mode: "mock" | "real", fps = 15) =>
    request<{ ok: boolean; run_id: string; is_simulated: boolean; message: string }>(
      "/api/v1/runs",
      { method: "POST", body: { mode, fps } },
    ),

  stopRun: () =>
    request<{ ok: boolean; message: string }>("/api/v1/runs/stop", { method: "POST" }),

  // Regions
  listRegions: () => request<{ items: RegionModel[] }>("/api/v1/regions"),

  createRegion: (body: { region_id?: string; name: string; polygon: { points: { x: number; y: number }[] }; enabled?: boolean }) =>
    request<RegionModel>("/api/v1/regions", { method: "POST", body }),

  updateRegion: (
    regionId: string,
    body: { name: string; polygon: { points: { x: number; y: number }[] }; enabled?: boolean },
  ) => request<RegionModel>(`/api/v1/regions/${regionId}`, { method: "PUT", body }),

  deleteRegion: (regionId: string) =>
    request<{ ok: boolean; deleted: string }>(`/api/v1/regions/${regionId}`, {
      method: "DELETE",
    }),

  // Rules
  listRules: () => request<{ items: RuleDefinition[] }>("/api/v1/rules"),

  getRule: (ruleId: string) => request<RuleDefinition>(`/api/v1/rules/${ruleId}`),

  createRule: (body: {
    name: string;
    description?: string;
    type: RuleType;
    config: Partial<RuleConfig>;
    severity: Severity;
    enabled?: boolean;
  }) => request<RuleDefinition>("/api/v1/rules", { method: "POST", body }),

  updateRule: (
    ruleId: string,
    body: {
      name?: string;
      description?: string;
      config?: Partial<RuleConfig>;
      severity?: Severity;
      enabled?: boolean;
    },
  ) => request<RuleDefinition>(`/api/v1/rules/${ruleId}`, { method: "PATCH", body }),

  listRuleVersions: (ruleId: string) =>
    request<{ items: RuleVersionEntry[] }>(`/api/v1/rules/${ruleId}/versions`),

  testRule: (ruleId: string, observations: unknown[]) =>
    request<{
      rule_id: string;
      rule_version: number;
      evaluated_observations: number;
      evaluation_count: number;
      would_trigger_count: number;
      dry_run: boolean;
      evaluations: unknown[];
      note: string;
    }>(`/api/v1/rules/${ruleId}/test`, { method: "POST", body: { observations } }),

  sampleTestRule: (ruleId: string) =>
    request<{
      rule_id: string;
      evaluated_observations: number;
      would_trigger_count: number;
      dry_run: boolean;
      evaluations: unknown[];
      note: string;
    }>(`/api/v1/rules/${ruleId}/sample-test`, { method: "POST" }),

  // Events
  listEvents: (params: {
    limit?: number;
    offset?: number;
    severity?: string;
    status?: string;
    rule_id?: string;
    run_id?: string;
    source_id?: string;
    search?: string;
    since?: string;
    until?: string;
    sort?: string;
    order?: string;
  }) => request<Paginated<IncidentEvent>>("/api/v1/events", { query: params }),

  getEvent: (eventId: string) =>
    request<{ event: IncidentEvent; audit: AuditEntry[] }>(`/api/v1/events/${eventId}`),

  updateEventStatus: (
    eventId: string,
    body: { action: "acknowledge" | "resolve" | "dismiss" | "reopen" | "annotate"; actor?: string; note?: string },
  ) =>
    request<{ ok: boolean; event: IncidentEvent }>(`/api/v1/events/${eventId}`, {
      method: "PATCH",
      body,
    }),

  listEventAudit: (eventId: string) =>
    request<{ items: AuditEntry[] }>(`/api/v1/events/${eventId}/audit`),

  eventsExportUrl: (format: "json" | "csv", params?: Record<string, string>) => {
    const qs = new URLSearchParams({ format, ...(params ?? {}) }).toString();
    return `${API_BASE_URL}/api/v1/events/export?${qs}`;
  },

  rulesExportUrl: () => `${API_BASE_URL}/api/v1/rules/export`,

  // Analytics
  analyticsSummary: (windowHours = 24, runId?: string) =>
    request<AnalyticsSummary>("/api/v1/analytics/summary", {
      query: { window_hours: windowHours, run_id: runId },
    }),

  // Pipeline
  pipelineStatus: () =>
    request<{ pipeline: PipelineInfo; measurement_note: string }>("/api/v1/pipeline/status"),

  pipelinePreflight: () => request<PipelinePreflight>("/api/v1/pipeline/preflight"),

  pipelineExportInfo: () =>
    request<{ export_dir: string; evidence_dir: string; pipegen_export_dir: string | null }>(
      "/api/v1/pipeline/export",
    ),

  // System
  systemStatusDetail: () => request<SystemStatus>("/api/v1/system/status"),

  systemConfigDetail: () =>
    request<{ config: Record<string, unknown> }>("/api/v1/system/config"),

  // Evidence
  evidenceStatus: () => request<EvidenceStatusSummary>("/api/v1/evidence/status"),

  updateArtifact: (
    artifactId: string,
    body: { path?: string; status?: string; notes?: string },
  ) => request<{ artifact_id: string; status: string; path: string; notes: string }>(
    `/api/v1/evidence/${artifactId}`,
    { method: "PUT", body },
  ),

  verifyArtifact: (
    artifactId: string,
    body: { status: "verified" | "invalid" | "captured" | "pending" | "missing"; notes?: string },
  ) =>
    request<{ artifact_id: string; status: string; verified_at: string | null; notes: string }>(
      `/api/v1/evidence/${artifactId}/verify`,
      { method: "POST", body },
    ),

  // Health check
  healthCheck: () => request<HealthResponse>("/health"),
};

/** Type guard used by the live scene to narrow a WebSocket payload. */
export function asObservationFrame(payload: unknown): ObservationFrame | null {
  if (!payload || typeof payload !== "object") return null;
  const candidate = payload as Partial<ObservationFrame>;
  if (typeof candidate.observation_id !== "string") return null;
  if (!Array.isArray(candidate.entities)) return null;
  return candidate as ObservationFrame;
}
