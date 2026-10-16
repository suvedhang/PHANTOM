import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { IncidentEvent } from "../api/types";
import { Badge } from "../components/Badge";
import { Card, CardBody, CardHeader } from "../components/Card";
import { LineChart } from "../components/Charts";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { StatTile } from "../components/StatTile";
import { DataTable, type Column } from "../components/Table";
import { useApi } from "../hooks/useApi";
import { useApp } from "../hooks/useApp";
import { formatDateTime, formatDuration, humanizeToken, relativeTime } from "../lib/format";
import { EVENT_STATUS_META, SEVERITY_META } from "../lib/severity";

function severityBadge(severity: IncidentEvent["severity"]) {
  const meta = SEVERITY_META[severity];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

function statusBadge(status: IncidentEvent["status"]) {
  const meta = EVENT_STATUS_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function OverviewPage() {
  const { status, eventsRevision } = useApp();
  const analytics = useApi(() => api.analyticsSummary(24), [eventsRevision], {
    pollMs: 15000,
  });
  const recent = useApi(() => api.listEvents({ limit: 6, sort: "created_at", order: "desc" }), [
    eventsRevision,
  ], { pollMs: 8000 });

  const pipeline = status?.pipeline;
  const summary = analytics.data;

  const overTime = (summary?.events_over_time ?? []).map((bucket) => ({
    label: String(bucket.bucket_start ?? ""),
    value: Number(bucket.count ?? 0),
  }));

  const columns: Column<IncidentEvent>[] = [
    {
      key: "severity",
      header: "Severity",
      render: (row) => severityBadge(row.severity),
      sortable: true,
      sortValue: (row) => row.severity,
    },
    {
      key: "title",
      header: "Incident",
      render: (row) => (
        <div className="stack" style={{ gap: 2 }}>
          <span>{row.title}</span>
          <span className="dim mono" style={{ fontSize: "var(--fs-xs)" }}>
            {row.rule_id} · v{row.rule_version}
          </span>
        </div>
      ),
    },
    { key: "status", header: "Status", render: (row) => statusBadge(row.status) },
    {
      key: "last_seen",
      header: "Last seen",
      render: (row) => <span title={formatDateTime(row.last_seen)}>{relativeTime(row.last_seen)}</span>,
      sortable: true,
      sortValue: (row) => row.last_seen,
    },
    {
      key: "sim",
      header: "Origin",
      render: (row) =>
        row.is_simulated ? <Badge tone="warn">Simulated</Badge> : <Badge tone="info">Observed</Badge>,
    },
  ];

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Overview"
        description="Current run, incident volume, pipeline health, and the most recent incidents."
        actions={
          <>
            <Link className="btn btn-secondary btn-sm" to="/live">
              Open live scene
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/events">
              All events
            </Link>
          </>
        }
      />

      {analytics.error && !analytics.data ? (
        <ErrorState error={analytics.error} onRetry={analytics.reload} />
      ) : analytics.loading && !summary ? (
        <LoadingPanel rows={3} />
      ) : (
        <div className="grid grid-4">
          <StatTile
            label="Active incidents"
            value={summary?.active_events ?? 0}
            tone={(summary?.active_events ?? 0) > 0 ? "warn" : "ok"}
            foot="Status active or acknowledged"
          />
          <StatTile
            label="Events (24h)"
            value={summary?.total_events ?? 0}
            foot={`${summary?.sample_count ?? 0} events in window`}
          />
          <StatTile
            label="Avg active duration"
            value={formatDuration(summary?.average_active_duration_seconds ?? null)}
            foot="First seen to last seen"
          />
          <StatTile
            label="Pipeline"
            value={pipeline ? humanizeToken(pipeline.status) : "-"}
            tone={pipeline?.status === "running" || pipeline?.status === "simulated" ? "ok" : "neutral"}
            foot={pipeline?.message ?? "No active run"}
          />
        </div>
      )}

      <div className="grid grid-2">
        <Card>
          <CardHeader
            title="Event rate"
            subtitle="Hourly buckets, events per hour (24h window)"
            actions={
              summary?.is_simulated ? <Badge tone="warn">Includes simulated</Badge> : null
            }
          />
          <CardBody>
            <LineChart data={overTime} unit="events / hour" />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Pipeline health"
            subtitle="Reported by the pipeline adapter"
            actions={
              <Link className="btn btn-ghost btn-sm" to="/pipeline">
                Details
              </Link>
            }
          />
          <CardBody>
            {pipeline ? (
              <dl className="kv">
                <dt>Mode</dt>
                <dd>{pipeline.mode}</dd>
                <dt>Adapter</dt>
                <dd>
                  {pipeline.adapter} ({pipeline.adapter_kind})
                </dd>
                <dt>Status</dt>
                <dd>{humanizeToken(pipeline.status)}</dd>
                <dt>Model</dt>
                <dd>{pipeline.model_id ?? "not reported"}</dd>
                <dt>Precision</dt>
                <dd>{pipeline.precision ?? "not reported"}</dd>
                <dt>Last frame</dt>
                <dd>{relativeTime(pipeline.last_successful_frame_at)}</dd>
              </dl>
            ) : (
              <EmptyState title="No pipeline status" message="Start a run to see live pipeline data." />
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Recent incidents"
          subtitle="Newest events across all rules"
          actions={
            <Link className="btn btn-ghost btn-sm" to="/events">
              View all
            </Link>
          }
        />
        <CardBody pad={false}>
          {recent.error && !recent.data ? (
            <div style={{ padding: "var(--sp-4)" }}>
              <ErrorState error={recent.error} onRetry={recent.reload} />
            </div>
          ) : (
            <DataTable
              columns={columns}
              rows={recent.data?.items ?? []}
              rowKey={(row) => row.event_id}
              loading={recent.loading && !recent.data}
              empty={
                <EmptyState
                  title="No events yet"
                  message="Start a simulated run from the top bar to generate deterministic demo incidents."
                />
              }
            />
          )}
        </CardBody>
      </Card>
    </div>
  );
}
