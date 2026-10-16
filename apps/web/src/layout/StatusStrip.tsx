import { useApp } from "../hooks/useApp";

import "./layout.css";

type Tone = "ok" | "warn" | "danger" | "info" | "neutral";

function StatusItemChip({
  label,
  value,
  tone,
  pulse,
}: {
  label: string;
  value: string;
  tone: Tone;
  pulse?: boolean;
}) {
  return (
    <div className="status-item">
      <span className="status-label">{label}</span>
      <span className={`status-chip tone-${tone}`}>
        <span
          className={`status-dot ${pulse ? "status-dot-pulse" : ""}`}
          aria-hidden="true"
        />
        {value}
      </span>
    </div>
  );
}

function socketToneOf(state: string): { label: string; tone: Tone } {
  if (state === "open") return { label: "Live", tone: "ok" };
  if (state === "connecting") return { label: "Connecting", tone: "warn" };
  return { label: "Offline", tone: "danger" };
}

export function StatusStrip() {
  const { status, socketState } = useApp();

  const source = status?.source_status ?? "unavailable";
  const sourceMode = status?.pipeline.mode ?? "disconnected";
  const pipeline = status?.pipeline.status ?? "not_configured";
  const transport = status?.transport.status ?? "disabled";
  const lastEvent = status?.last_event_at ?? null;
  const sim = status?.pipeline.is_simulated ?? false;
  const socket = socketToneOf(socketState);

  const sourceTone: Tone =
    source === "connected"
      ? "ok"
      : source === "stale" || source === "connecting"
        ? "warn"
        : source === "invalid"
          ? "danger"
          : "neutral";
  const pipelineTone: Tone =
    pipeline === "running" || pipeline === "simulated"
      ? "ok"
      : pipeline === "starting" || pipeline === "stopping" || pipeline === "configured"
        ? "warn"
        : pipeline === "failed"
          ? "danger"
          : "neutral";
  const transportTone: Tone =
    transport === "connected"
      ? "ok"
      : transport === "reconnecting"
        ? "warn"
        : transport === "failed"
          ? "danger"
          : "neutral";

  return (
    <div className="status-strip" role="group" aria-label="System status">
      <StatusItemChip
        label="Mode"
        value={sourceMode.replace(/_/g, " ")}
        tone={sim ? "warn" : "info"}
      />
      <StatusItemChip label="Source" value={source.replace(/_/g, " ")} tone={sourceTone} />
      <StatusItemChip
        label="Pipeline"
        value={pipeline.replace(/_/g, " ")}
        tone={pipelineTone}
      />
      <StatusItemChip label="Transport" value={transport} tone={transportTone} />
      <StatusItemChip
        label="Live socket"
        value={socket.label}
        tone={socket.tone}
        pulse={socketState === "open"}
      />
      <StatusItemChip
        label="Last event"
        value={lastEvent ? new Date(lastEvent).toLocaleTimeString() : "none"}
        tone="neutral"
      />
    </div>
  );
}
