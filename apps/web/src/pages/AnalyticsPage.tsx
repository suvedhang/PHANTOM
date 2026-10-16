import { useState } from "react";

import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { Card, CardBody, CardHeader } from "../components/Card";
import { BarChart, LineChart, type ChartDatum } from "../components/Charts";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { StatTile } from "../components/StatTile";
import { useApi } from "../hooks/useApi";
import { formatDuration, formatTime, humanizeToken } from "../lib/format";
import { EVENT_STATUS_META, SEVERITY_META } from "../lib/severity";

const WINDOWS = [
  { label: "1 h", hours: 1 },
  { label: "6 h", hours: 6 },
  { label: "24 h", hours: 24 },
  { label: "72 h", hours: 72 },
  { label: "7 d", hours: 168 },
];

export function AnalyticsPage() {
  const [hours, setHours] = useState(24);
  const summary = useApi(() => api.analyticsSummary(hours), [hours], { pollMs: 15000 });

  const data = summary.data;

  const severityData: ChartDatum[] = Object.entries(data?.events_by_severity ?? {})
    .filter(([, count]) => count > 0)
    .map(([severity, count]) => ({
      label: SEVERITY_META[severity as keyof typeof SEVERITY_META]?.label ?? humanizeToken(severity),
      value: count,
    }));

  const ruleData: ChartDatum[] = Object.entries(data?.events_by_rule ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([rule, count]) => ({ label: rule, value: count }));

  const overTime: ChartDatum[] = (data?.events_over_time ?? []).map((entry) => {
    const bucket = entry as { bucket_start?: string; count?: number };
    return {
      label: formatTime(bucket.bucket_start),
      value: typeof bucket.count === "number" ? bucket.count : 0,
    };
  });

  const activeCount = data?.events_by_status?.active ?? 0;

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Analytics"
        description="Deterministic aggregates over durable events for the selected window."
        actions={
          <div className="row wrap" style={{ gap: "var(--sp-2)" }}>
            {WINDOWS.map((w) => (
              <button
                key={w.hours}
                type="button"
                className={`btn btn-sm ${hours === w.hours ? "btn-primary" : "btn-ghost"}`}
                aria-pressed={hours === w.hours}
                onClick={() => setHours(w.hours)}
              >
                {w.label}
              </button>
            ))}
          </div>
        }
      />

      {summary.error ? (
        <ErrorState error={summary.error} onRetry={summary.reload} />
      ) : summary.loading && !data ? (
        <LoadingPanel rows={5} />
      ) : !data ? (
        <EmptyState title="No analytics" message="Analytics are unavailable." />
      ) : (
        <>
          {data.is_simulated && (
            <div className="sim-banner" role="note">
              <strong>SIMULATED DATA</strong>
              <span>
                This window includes events generated from the deterministic demo scenario, not
                real observations.
              </span>
            </div>
          )}

          <div className="grid stat-grid">
            <StatTile label="Total events" value={data.total_events} foot={`last ${hours} h`} />
            <StatTile
              label="Currently active"
              value={activeCount}
              tone={activeCount > 0 ? "danger" : "neutral"}
              foot="status = active"
            />
            <StatTile
              label="Avg active duration"
              value={formatDuration(data.average_active_duration_seconds)}
              foot="active → resolved"
            />
            <StatTile
              label="Distinct rules fired"
              value={Object.keys(data.events_by_rule).length}
              foot="by rule_id"
            />
          </div>

          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <Card>
              <CardHeader title="Events over time" subtitle="Count per hourly bucket" />
              <CardBody>
                <LineChart data={overTime} unit="events / hour" height={150} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="By severity" subtitle="Count per severity band" />
              <CardBody>
                <BarChart data={severityData} unit="events" />
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader title="Top rules" subtitle="Most frequent rule_id (top 8)" />
            <CardBody>
              <BarChart data={ruleData} unit="events" />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="By status" />
            <CardBody>
              <div className="row wrap" style={{ gap: "var(--sp-2)" }}>
                {Object.entries(data.events_by_status).length === 0 ? (
                  <span className="dim">No statuses in this window.</span>
                ) : (
                  Object.entries(data.events_by_status).map(([status, count]) => (
                    <Badge
                      key={status}
                      tone={
                        EVENT_STATUS_META[status as keyof typeof EVENT_STATUS_META]?.tone ??
                        "neutral"
                      }
                    >
                      {humanizeToken(status)}: {count}
                    </Badge>
                  ))
                )}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Method notes"
              subtitle={`Window: ${hours} h · ${data.sample_count} sample(s)`}
            />
            <CardBody>
              {data.notes.length === 0 ? (
                <EmptyState title="No notes" />
              ) : (
                <ul className="notes-list">
                  {data.notes.map((note, index) => (
                    <li key={index}>{note}</li>
                  ))}
                </ul>
              )}
              <p className="dim" style={{ fontSize: "var(--fs-sm)", marginTop: 10 }}>
                All figures are computed from stored events. No metrics are estimated or
                fabricated.
              </p>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
