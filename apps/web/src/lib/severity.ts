import type {
  EvidenceStatus,
  EventStatus,
  PipelineStatus,
  Severity,
  SourceStatus,
  TransportStatus,
} from "../api/types";

export type StatusTone = "neutral" | "info" | "ok" | "warn" | "danger";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
}

/** Severity is paired with a text label (never color alone). */
export const SEVERITY_META: Record<Severity, StatusMeta> = {
  critical: { label: "Critical", tone: "danger" },
  high: { label: "High", tone: "danger" },
  medium: { label: "Medium", tone: "warn" },
  low: { label: "Low", tone: "info" },
  info: { label: "Info", tone: "neutral" },
};

export const EVENT_STATUS_META: Record<EventStatus, StatusMeta> = {
  active: { label: "Active", tone: "danger" },
  acknowledged: { label: "Acknowledged", tone: "warn" },
  resolved: { label: "Resolved", tone: "ok" },
  dismissed: { label: "Dismissed", tone: "neutral" },
};

export const PIPELINE_STATUS_META: Record<PipelineStatus, StatusMeta> = {
  not_configured: { label: "Not configured", tone: "neutral" },
  configured: { label: "Configured", tone: "info" },
  starting: { label: "Starting", tone: "warn" },
  running: { label: "Running", tone: "ok" },
  stopping: { label: "Stopping", tone: "warn" },
  stopped: { label: "Stopped", tone: "neutral" },
  failed: { label: "Failed", tone: "danger" },
  simulated: { label: "Simulated", tone: "info" },
};

export const SOURCE_STATUS_META: Record<SourceStatus, StatusMeta> = {
  unavailable: { label: "Unavailable", tone: "neutral" },
  connecting: { label: "Connecting", tone: "warn" },
  connected: { label: "Connected", tone: "ok" },
  stale: { label: "Stale", tone: "warn" },
  disconnected: { label: "Disconnected", tone: "neutral" },
  invalid: { label: "Invalid", tone: "danger" },
};

export const TRANSPORT_STATUS_META: Record<TransportStatus, StatusMeta> = {
  disabled: { label: "Disabled", tone: "neutral" },
  connected: { label: "Connected", tone: "ok" },
  reconnecting: { label: "Reconnecting", tone: "warn" },
  failed: { label: "Failed", tone: "danger" },
};

export const PIPELINE_STATUS_TONE: Record<PipelineStatus, StatusTone> = {
  not_configured: "neutral",
  configured: "info",
  starting: "warn",
  running: "ok",
  stopping: "warn",
  stopped: "neutral",
  failed: "danger",
  simulated: "info",
};

export const EVIDENCE_STATUS_META: Record<EvidenceStatus, StatusMeta> = {
  missing: { label: "Missing", tone: "danger" },
  pending: { label: "Pending", tone: "warn" },
  captured: { label: "Captured", tone: "info" },
  verified: { label: "Verified", tone: "ok" },
  invalid: { label: "Invalid", tone: "danger" },
};

export const SOURCE_MODE_META: Record<string, StatusMeta> = {
  live: { label: "Live", tone: "ok" },
  file: { label: "File", tone: "info" },
  simulated: { label: "Simulated", tone: "warn" },
  disconnected: { label: "Disconnected", tone: "neutral" },
};

export function sourceStatusMeta(status: SourceStatus): StatusMeta {
  return SOURCE_STATUS_META[status] ?? { label: status, tone: "neutral" };
}

export function transportStatusMeta(status: TransportStatus): StatusMeta {
  return TRANSPORT_STATUS_META[status] ?? { label: status, tone: "neutral" };
}

export function pipelineStatusMeta(status: PipelineStatus): StatusMeta {
  return PIPELINE_STATUS_META[status] ?? { label: status, tone: "neutral" };
}
