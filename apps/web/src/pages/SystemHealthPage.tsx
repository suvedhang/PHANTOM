import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { StatTile } from "../components/StatTile";
import { useApi } from "../hooks/useApi";
import { useApp } from "../hooks/useApp";
import {
  PIPELINE_STATUS_META,
  SOURCE_STATUS_META,
  TRANSPORT_STATUS_META,
} from "../lib/severity";

export function SystemHealthPage() {
  const { status, socketState, liveCounters, refresh, error, loading } = useApp();
  const health = useApi(() => api.health(), [], { pollMs: 10000 });

  const heartbeatLabel = liveCounters.lastHeartbeat
    ? new Date(liveCounters.lastHeartbeat).toLocaleTimeString()
    : "never";

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="System Health"
        description="Live process, transport, and source diagnostics."
        actions={
          <Button variant="ghost" onClick={() => { refresh(); health.reload(); }} loading={health.refreshing}>
            Refresh
          </Button>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : loading && !status ? (
        <LoadingPanel rows={5} />
      ) : (
        <>
          <div className="grid stat-grid">
            <StatTile
              label="API health"
              value={
                health.data ? (
                  <Badge tone={health.data.status === "ok" ? "ok" : "warn"}>
                    {health.data.status}
                  </Badge>
                ) : (
                  "-"
                )
              }
              foot={health.data?.app ?? health.data?.detail}
            />
            <StatTile
              label="Socket"
              value={
                <Badge tone={socketState === "open" ? "ok" : socketState === "connecting" ? "warn" : "danger"}>
                  {socketState}
                </Badge>
              }
              foot={`heartbeat: ${heartbeatLabel}`}
            />
            <StatTile label="Observations received" value={liveCounters.observations} foot="this session" />
            <StatTile label="Event frames received" value={liveCounters.events} foot="this session" />
          </div>

          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <Card>
              <CardHeader title="Sources & transport" />
              <CardBody>
                {!status ? (
                  <EmptyState title="No status" message="System status unavailable." />
                ) : (
                  <dl className="kv">
                    <dt>Pipeline status</dt>
                    <dd>
                      <Badge tone={PIPELINE_STATUS_META[status.pipeline.status].tone}>
                        {PIPELINE_STATUS_META[status.pipeline.status].label}
                      </Badge>
                    </dd>
                    <dt>Source status</dt>
                    <dd>
                      <Badge tone={SOURCE_STATUS_META[status.source_status].tone}>
                        {SOURCE_STATUS_META[status.source_status].label}
                      </Badge>
                    </dd>
                    <dt>Transport</dt>
                    <dd>
                      <Badge
                        tone={
                          TRANSPORT_STATUS_META[
                            status.transport?.status as keyof typeof TRANSPORT_STATUS_META
                          ]?.tone ?? "neutral"
                        }
                      >
                        {TRANSPORT_STATUS_META[
                          status.transport?.status as keyof typeof TRANSPORT_STATUS_META
                        ]?.label ?? status.transport?.status ?? "-"}
                      </Badge>
                    </dd>
                    <dt>Active run</dt>
                    <dd className="mono truncate">{status.active_run_id ?? "-"}</dd>
                  </dl>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Pipeline" />
              <CardBody>
                {!status ? (
                  <EmptyState title="No pipeline" />
                ) : (
                  <dl className="kv">
                    <dt>Status</dt>
                    <dd>
                      <Badge tone={PIPELINE_STATUS_META[status.pipeline.status].tone}>
                        {PIPELINE_STATUS_META[status.pipeline.status].label}
                      </Badge>
                    </dd>
                    <dt>Mode</dt>
                    <dd>{status.pipeline.mode}</dd>
                    <dt>Adapter</dt>
                    <dd>
                      {status.pipeline.adapter} · {status.pipeline.adapter_kind}
                    </dd>
                    <dt>Stale</dt>
                    <dd>{status.pipeline.stale ? "yes" : "no"}</dd>
                    <dt>Last observation</dt>
                    <dd>{status.pipeline.last_observation_at ?? "never"}</dd>
                    <dt>Last frame</dt>
                    <dd>{status.pipeline.last_successful_frame_at ?? "never"}</dd>
                    <dt>Message</dt>
                    <dd>{status.pipeline.message}</dd>
                  </dl>
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Recent errors"
              subtitle="Recorded by the backend since startup"
            />
            <CardBody>
              {!status || status.recent_errors.length === 0 ? (
                <EmptyState title="No recent errors" message="Nothing has been logged." />
              ) : (
                <div className="stack" style={{ gap: "var(--sp-2)" }}>
                  {status.recent_errors.map((err, index) => (
                    <div key={index} className="row-between">
                      <span className="mono" style={{ fontSize: "var(--fs-sm)" }}>
                        {err}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Transport counters" />
            <CardBody>
              {!status ? (
                <EmptyState title="No transport" />
              ) : (
                <div className="grid stat-grid">
                  <StatTile label="Clients" value={status.transport ? String(socketState) : "-"} />
                  <StatTile label="Heartbeat" value={heartbeatLabel} />
                  <StatTile label="Run" value={status.pipeline.status} small />
                  <StatTile label="Last frame" value={status.pipeline.last_successful_frame_at ? "yes" : "no"} />
                  <StatTile label="Checked at" value={new Date().toLocaleTimeString()} />
                </div>
              )}
            </CardBody>
          </Card>

          <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
            Heartbeat times are shown in your local timezone. All timestamps from the API are UTC.
            {health.data?.version && ` Backend version: ${health.data.version}.`}
          </p>
        </>
      )}
    </div>
  );
}
