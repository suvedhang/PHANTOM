import { useState } from "react";

import { api } from "../api/client";
import type { PipelinePreflight, RunMode } from "../api/types";
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
import { useToast } from "../hooks/useToast";
import { formatDateTime, relativeTime } from "../lib/format";
import { PIPELINE_STATUS_META, SOURCE_MODE_META } from "../lib/severity";

export function PipelinePage() {
  const toast = useToast();
  const { status, refresh } = useApp();
  const [busy, setBusy] = useState(false);

  const preflight = useApi(() => api.pipelinePreflight(), []);
  const pipelineStatus = useApi(() => api.pipelineStatus(), [], { pollMs: 5000 });
  const exportInfo = useApi(() => api.pipelineExportInfo(), []);

  const pipeline = status?.pipeline ?? pipelineStatus.data?.pipeline ?? null;
  const mode = pipeline?.mode as RunMode | undefined;

  const start = async (runMode: "mock" | "real") => {
    setBusy(true);
    try {
      const result = await api.startRun(runMode, 8);
      toast.ok("Run started", `${runMode} mode · ${result.run_id}`);
      preflight.reload();
      pipelineStatus.reload();
      refresh();
    } catch (err) {
      toast.error("Could not start run", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.stopRun();
      toast.ok("Run stopped");
      pipelineStatus.reload();
      refresh();
    } catch (err) {
      toast.error("Could not stop run", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Pipeline"
        description="Adapter status, readiness checks, and run control. Real execution requires a verified PipeGen host."
        actions={
          <div className="row" style={{ gap: "var(--sp-2)" }}>
            <Button variant="primary" onClick={() => start("mock")} loading={busy}>
              Start simulated
            </Button>
            <Button
              variant="secondary"
              onClick={() => start("real")}
              disabled={busy || !(preflight.data?.ready_to_run ?? false)}
              title={
                preflight.data?.ready_to_run
                  ? "Start the real PipeGen adapter"
                  : preflight.data?.blocker ?? "Real pipeline not ready"
              }
            >
              Start real
            </Button>
            <Button variant="ghost" onClick={stop} disabled={!status?.active_run_id || busy}>
              Stop
            </Button>
          </div>
        }
      />

      {pipeline?.is_simulated && (
        <div className="sim-banner" role="note">
          <strong>SIMULATED SOURCE</strong>
          <span>
            The active run uses the mock adapter. No GPU telemetry, PipeGen version, or real model
            metrics are reported.
          </span>
        </div>
      )}

      <div className="grid stat-grid">
        <StatTile
          label="Status"
          value={
            pipeline ? (
              <Badge tone={PIPELINE_STATUS_META[pipeline.status].tone}>
                {PIPELINE_STATUS_META[pipeline.status].label}
              </Badge>
            ) : (
              "-"
            )
          }
        />
        <StatTile
          label="Mode"
          value={
            mode ? (
              <Badge tone={SOURCE_MODE_META[mode]?.tone ?? "neutral"}>
                {SOURCE_MODE_META[mode]?.label ?? mode}
              </Badge>
            ) : (
              "-"
            )
          }
        />
        <StatTile label="Adapter" value={pipeline?.adapter ?? "-"} small foot={pipeline?.adapter_kind} />
        <StatTile
          label="Last frame"
          value={relativeTime(pipeline?.last_successful_frame_at)}
          foot={formatDateTime(pipeline?.last_successful_frame_at)}
        />
      </div>

      <Card>
        <CardHeader
          title="Readiness checks"
          subtitle={
            preflight.data
              ? preflight.data.configured
                ? "PipeGen adapter configured"
                : "PipeGen adapter not configured"
              : ""
          }
          actions={
            <Button size="sm" variant="ghost" onClick={preflight.reload} loading={preflight.refreshing}>
              Re-run
            </Button>
          }
        />
        <CardBody>
          {preflight.error ? (
            <ErrorState error={preflight.error} onRetry={preflight.reload} />
          ) : preflight.loading && !preflight.data ? (
            <LoadingPanel rows={4} />
          ) : (
            <PreflightView preflight={preflight.data} />
          )}
        </CardBody>
      </Card>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Card>
          <CardHeader title="Pipeline detail" />
          <CardBody>
            {!pipeline ? (
              <EmptyState title="No pipeline" message="Status unavailable." />
            ) : (
              <dl className="kv">
                <dt>Status</dt>
                <dd>{pipeline.status}</dd>
                <dt>Configured</dt>
                <dd>{pipeline.configured ? "yes" : "no"}</dd>
                <dt>Stale</dt>
                <dd>{pipeline.stale ? "yes" : "no"}</dd>
                <dt>Retry count</dt>
                <dd>{pipeline.retry_count}</dd>
                <dt>Recoverable</dt>
                <dd>{pipeline.recoverable ? "yes" : "no"}</dd>
                <dt>Model ID</dt>
                <dd className="mono">{pipeline.model_id ?? "-"}</dd>
                <dt>Message</dt>
                <dd>{pipeline.message}</dd>
                {pipelineStatus.data?.measurement_note && (
                  <>
                    <dt>Measurement note</dt>
                    <dd className="dim">{pipelineStatus.data.measurement_note}</dd>
                  </>
                )}
              </dl>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Export locations" subtitle="Where artifacts and exports are written" />
          <CardBody>
            {exportInfo.error ? (
              <ErrorState error={exportInfo.error} onRetry={exportInfo.reload} />
            ) : exportInfo.loading && !exportInfo.data ? (
              <LoadingPanel rows={3} />
            ) : (
              <dl className="kv">
                <dt>Export dir</dt>
                <dd className="mono truncate">{exportInfo.data?.export_dir ?? "-"}</dd>
                <dt>Evidence dir</dt>
                <dd className="mono truncate">{exportInfo.data?.evidence_dir ?? "-"}</dd>
                <dt>PipeGen export dir</dt>
                <dd className="mono truncate">
                  {exportInfo.data?.pipegen_export_dir ?? "not configured"}
                </dd>
              </dl>
            )}
          </CardBody>
        </Card>
      </div>

      <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
        In demo mode the pipeline uses the mock adapter and reports no hardware metrics, GPU
        utilisation, or PipeGen versions. Those fields stay null until a real adapter verifies
        them against a configured host.
      </p>
    </div>
  );
}

function PreflightView({ preflight }: { preflight: PipelinePreflight | null }) {
  if (!preflight) {
    return <EmptyState title="No preflight data" />;
  }
  return (
    <div className="stack" style={{ gap: "var(--sp-3)" }}>
      <div className="row wrap" style={{ gap: "var(--sp-2)" }}>
        <Badge tone={preflight.ready_to_run ? "ok" : "warn"}>
          {preflight.ready_to_run ? "Ready to run" : "Not ready"}
        </Badge>
        <Badge tone={preflight.configured ? "info" : "neutral"}>
          {preflight.configured ? "Configured" : "Not configured"}
        </Badge>
        {preflight.expected_version && (
          <Badge tone="neutral">expected v{preflight.expected_version}</Badge>
        )}
      </div>
      {!preflight.ready_to_run && preflight.blocker && (
        <div className="error-state" role="alert">
          <div className="error-state-head">
            <span className="error-state-mark" aria-hidden="true">
              !
            </span>
            <div>
              <h3 className="error-state-title">Blocker</h3>
              <p className="error-state-message">{preflight.blocker}</p>
            </div>
          </div>
        </div>
      )}
      <div className="stack" style={{ gap: "var(--sp-2)" }}>
        {preflight.checks.map((check) => (
          <div key={check.name} className="row-between">
            <div className="stack" style={{ gap: 0 }}>
              <span>{check.name}</span>
              <span className="dim" style={{ fontSize: "var(--fs-xs)" }}>
                {check.detail}
              </span>
            </div>
            <Badge tone={check.passed ? "ok" : "danger"}>
              {check.passed ? "Pass" : "Fail"}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}
