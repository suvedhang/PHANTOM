/**
 * PHANTOM API types.
 *
 * These mirror the Pydantic contracts in `apps/api/phantom_api/schemas.py`
 * (schema_version "1.0") and the JSON Schema copies in
 * `packages/contracts/schema`. Keep them in sync when the backend contract
 * changes.
 *
 * Geometry convention: normalized image coordinates in [0, 1], origin at the
 * top-left, +x right, +y down. Bounding boxes are [x_min, y_min, x_max, y_max].
 * Normalized units are image-space fractions, NOT metres.
 */

export const SCHEMA_VERSION = "1.0";

export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type EventStatus = "active" | "acknowledged" | "resolved" | "dismissed";
export type Provenance = "observed" | "derived" | "configured" | "simulated";
export type RunMode = "live" | "file" | "disconnected" | "simulated";
export type PipelineStatus =
  | "not_configured"
  | "configured"
  | "starting"
  | "running"
  | "stopping"
  | "stopped"
  | "failed"
  | "simulated";
export type SourceStatus =
  | "unavailable"
  | "connecting"
  | "connected"
  | "stale"
  | "disconnected"
  | "invalid";
export type TransportStatus = "disabled" | "connected" | "reconnecting" | "failed";
export type EvidenceStatus =
  | "missing"
  | "pending"
  | "captured"
  | "verified"
  | "invalid";
export type RuleType =
  | "region_entry"
  | "region_exit"
  | "dwell_time"
  | "wrong_way"
  | "count_threshold"
  | "sequence"
  | "unexpected_presence"
  | "motionless_track"
  | "boundary_crossing"
  | "baseline_deviation";

/** Rule types the deterministic engine actually supports today. */
export const SUPPORTED_RULE_TYPES: RuleType[] = [
  "region_entry",
  "region_exit",
  "dwell_time",
  "wrong_way",
  "count_threshold",
];

export interface Point {
  x: number;
  y: number;
}

export interface Polygon {
  points: Point[];
}

export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface NormalizedEntity {
  track_id: string | null;
  class_label: string;
  bbox: BoundingBox | null;
  confidence: number | null;
  provenance: Provenance;
}

export interface RegionModel {
  region_id: string;
  name: string;
  polygon: Polygon;
  enabled: boolean;
  version: number;
}

export interface RuleConfig {
  region_id: string | null;
  class_filter: string[];
  dwell_seconds: number | null;
  count_threshold: number | null;
  sustain_seconds: number | null;
  allowed_direction_deg: number | null;
  min_displacement: number | null;
  min_confidence: number | null;
  cooldown_seconds: number;
  dedup_seconds: number;
}

export interface RuleDefinition {
  rule_id: string;
  name: string;
  description: string;
  type: RuleType;
  config: RuleConfig;
  severity: Severity;
  enabled: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface RuleVersionEntry {
  version: number;
  snapshot: RuleDefinition;
  created_at: string;
}

export interface EventExplanation {
  human: string;
  machine: Record<string, unknown>;
  generated_by: "deterministic";
}

export interface IncidentEvent {
  schema_version: string;
  event_id: string;
  run_id: string;
  source_id: string;
  rule_id: string;
  rule_version: number;
  created_at: string;
  first_seen: string;
  last_seen: string;
  severity: Severity;
  status: EventStatus;
  title: string;
  provenance: Provenance;
  is_simulated: boolean;
  correlation_id: string | null;
  explanation: EventExplanation;
  evidence: Record<string, unknown>;
  track_ids: string[];
  observation_ids: string[];
  evidence_quality: number | null;
  closed_reason?: string | null;
}

export interface AuditEntry {
  audit_id: string;
  event_id?: string;
  action: string;
  actor: string;
  timestamp: string;
  note: string;
}

export interface PipelineInfo {
  status: PipelineStatus;
  mode: RunMode;
  adapter: string;
  adapter_kind: "mock" | "pipegen";
  configured: boolean;
  is_simulated: boolean;
  last_observation_at: string | null;
  last_successful_frame_at: string | null;
  stale: boolean;
  message: string;
  retry_count: number;
  recoverable: boolean;
  model_id: string | null;
  precision: string | null;
  engine_path: string | null;
  report_path: string | null;
  pipeline_version: string | null;
}

export interface TransportInfo {
  status: TransportStatus;
  connected_clients: number;
  published: number;
  failed: number;
  dropped: number;
  mqtt_enabled: boolean;
  mqtt_connected: boolean;
  mqtt_topic_prefix: string;
}

export interface SystemStatus {
  schema_version: string;
  timestamp: string;
  api_status: "ok" | "degraded";
  demo_mode: boolean;
  pipeline: PipelineInfo;
  transport: TransportInfo;
  source_status: SourceStatus;
  active_run_id: string | null;
  last_event_at: string | null;
  recent_errors: string[];
  config: Record<string, unknown>;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app: string;
  version: string;
  timestamp: string;
  database: "ok" | "error";
  detail: string;
}

export interface RunSummary {
  run_id: string;
  source_id: string;
  mode: string;
  status: string;
  adapter: string;
  is_simulated: boolean;
  pipeline_version: string | null;
  model_id: string | null;
  precision: string | null;
  engine_path: string | null;
  report_path: string | null;
  started_at: string | null;
  ended_at: string | null;
  last_observation_at: string | null;
  message: string;
}

export interface AnalyticsSummary {
  window_start: string;
  window_end: string;
  total_events: number;
  active_events: number;
  events_by_severity: Record<string, number>;
  events_by_rule: Record<string, number>;
  events_by_status: Record<string, number>;
  events_over_time: Array<Record<string, unknown>>;
  average_active_duration_seconds: number | null;
  is_simulated: boolean;
  sample_count: number;
  notes: string[];
}

export interface EvidenceArtifact {
  artifact_id: string;
  type: string;
  label: string;
  path: string;
  status: EvidenceStatus;
  required: boolean;
  notes: string;
  verified_at: string | null;
}

export interface EvidenceStatusSummary {
  items: EvidenceArtifact[];
  required_total: number;
  required_verified: number;
  missing_required: number;
  complete: boolean;
  note: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface PreflightCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface PipelinePreflight {
  configured: boolean;
  expected_version: string | null;
  checks: PreflightCheck[];
  ready_to_run: boolean;
  blocker: string;
}

export interface ApiErrorBody {
  error: string;
  code: string;
  detail?: string;
  correlation_id?: string | null;
}

/** Live scene payload broadcast over the WebSocket (`observation` messages). */
export interface ObservationFrame {
  observation_id: string;
  run_id: string;
  source_id: string;
  frame_index: number;
  timestamp: string;
  is_simulated: boolean;
  entities: NormalizedEntity[];
  tracks: Array<{
    track_id: string;
    class_label: string;
    provenance: Provenance;
    recent_positions: Point[];
  }>;
}

export type WsMessageType =
  | "connected"
  | "heartbeat"
  | "observation"
  | "run_status"
  | "event_created"
  | "event_updated";

export interface WsMessage {
  type: WsMessageType;
  ts: string | null;
  payload: unknown;
}
