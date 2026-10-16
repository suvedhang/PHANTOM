import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { AuditEntry, EventStatus, IncidentEvent, Severity } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { Drawer } from "../components/Dialog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/Table";
import { useApi } from "../hooks/useApi";
import { useApp } from "../hooks/useApp";
import { useToast } from "../hooks/useToast";
import { formatDateTime, humanizeToken, relativeTime } from "../lib/format";
import { EVENT_STATUS_META, SEVERITY_META } from "../lib/severity";

const PAGE_SIZE = 25;
const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];
const STATUSES: EventStatus[] = ["active", "acknowledged", "resolved", "dismissed"];

export function EventsPage() {
  const { eventsRevision } = useApp();
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<IncidentEvent | null>(null);

  const events = useApi(
    () =>
      api.listEvents({
        limit: PAGE_SIZE,
        offset,
        severity: severity || undefined,
        status: status || undefined,
        search: search || undefined,
      }),
    [search, severity, status, offset, eventsRevision],
    { pollMs: 8000 },
  );

  const exportParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (severity) params.severity = severity;
    if (status) params.status = status;
    if (search) params.search = search;
    return params;
  }, [search, severity, status]);

  const columns: Column<IncidentEvent>[] = [
    {
      key: "severity",
      header: "Sev",
      sortable: true,
      sortValue: (e) => SEVERITIES.indexOf(e.severity),
      render: (e) => (
        <Badge tone={SEVERITY_META[e.severity].tone}>{SEVERITY_META[e.severity].label}</Badge>
      ),
    },
    {
      key: "title",
      header: "Event",
      render: (e) => (
        <div className="stack" style={{ gap: 0 }}>
          <strong>{e.title}</strong>
          <span className="dim mono" style={{ fontSize: "var(--fs-xs)" }}>
            {e.event_id}
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (e) => (
        <Badge tone={EVENT_STATUS_META[e.status].tone}>{EVENT_STATUS_META[e.status].label}</Badge>
      ),
    },
    {
      key: "tracks",
      header: "Tracks",
      render: (e) => <span className="mono dim">{e.track_ids.join(", ") || "-"}</span>,
    },
    {
      key: "last_seen",
      header: "Last seen",
      sortable: true,
      sortValue: (e) => e.last_seen,
      render: (e) => <span className="dim" title={formatDateTime(e.last_seen)}>{relativeTime(e.last_seen)}</span>,
    },
    {
      key: "provenance",
      header: "Source",
      render: (e) => (
        <Badge tone={e.is_simulated ? "warn" : "info"}>
          {e.is_simulated ? "Simulated" : humanizeToken(e.provenance)}
        </Badge>
      ),
    },
  ];

  const atFirstPage = offset === 0;
  const atLastPage = !events.data || offset + PAGE_SIZE >= events.data.total;

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Events"
        description="Durable, explainable incidents derived from deterministic rule evaluations."
        actions={
          <div className="row" style={{ gap: "var(--sp-2)" }}>
            <a
              className="btn btn-secondary btn-sm"
              href={api.eventsExportUrl("json", exportParams)}
              target="_blank"
              rel="noreferrer"
            >
              Export JSON
            </a>
            <a
              className="btn btn-secondary btn-sm"
              href={api.eventsExportUrl("csv", exportParams)}
              target="_blank"
              rel="noreferrer"
            >
              Export CSV
            </a>
          </div>
        }
      />

      <Card>
        <CardHeader title="Filters" />
        <CardBody>
          <div className="form-grid">
            <label className="field">
              <span className="field-label">Search</span>
              <input
                className="input"
                value={search}
                placeholder="title, rule, track"
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
              />
            </label>
            <label className="field">
              <span className="field-label">Severity</span>
              <select
                className="input"
                value={severity}
                onChange={(e) => {
                  setSeverity(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All severities</option>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {SEVERITY_META[s].label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Status</span>
              <select
                className="input"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All statuses</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {EVENT_STATUS_META[s].label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Incidents"
          subtitle={
            events.data ? `${events.data.total} match(es)` : "Loading"
          }
          actions={
            <Button size="sm" variant="ghost" onClick={events.reload} loading={events.refreshing}>
              Refresh
            </Button>
          }
        />
        <CardBody>
          {events.error ? (
            <ErrorState error={events.error} onRetry={events.reload} />
          ) : events.loading && !events.data ? (
            <LoadingPanel rows={6} />
          ) : (
            <>
              <DataTable
                columns={columns}
                rows={events.data?.items ?? []}
                rowKey={(e) => e.event_id}
                onRowClick={(e) => setSelected(e)}
                caption="Incident events"
                empty={
                  <EmptyState
                    title="No events"
                    message="No incidents match the current filters. Start a simulated run to generate events."
                  />
                }
              />
              <div className="row-between" style={{ marginTop: "var(--sp-4)" }}>
                <span className="dim" style={{ fontSize: "var(--fs-sm)" }}>
                  {events.data && events.data.items.length > 0
                    ? `Showing ${events.data.offset + 1}-${Math.min(
                        events.data.offset + events.data.items.length,
                        events.data.total,
                      )} of ${events.data.total}`
                    : ""}
                </span>
                <div className="row" style={{ gap: "var(--sp-2)" }}>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={atFirstPage}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={atLastPage}
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      <EventDrawer
        event={selected}
        onClose={() => setSelected(null)}
        onChanged={events.reload}
      />
    </div>
  );
}

function EventDrawer({
  event,
  onClose,
  onChanged,
}: {
  event: IncidentEvent | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const detail = useApi(
    () => (event ? api.getEvent(event.event_id) : Promise.resolve(null)),
    [event?.event_id],
    { enabled: event !== null },
  );

  const current = detail.data?.event ?? event;
  const audit: AuditEntry[] = detail.data?.audit ?? [];

  const act = async (action: "acknowledge" | "resolve" | "dismiss" | "reopen" | "annotate") => {
    if (!current) return;
    setBusy(true);
    try {
      await api.updateEventStatus(current.event_id, {
        action,
        note: note.trim() || undefined,
      });
      toast.ok("Event updated", current.title);
      setNote("");
      detail.reload();
      onChanged();
    } catch (err) {
      toast.error("Action failed", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      open={event !== null}
      title={current?.title ?? "Event"}
      onClose={onClose}
      width={560}
      footer={
        current ? (
          <div className="row" style={{ gap: "var(--sp-2)", flexWrap: "wrap" }}>
            <Button size="sm" variant="primary" onClick={() => act("acknowledge")} loading={busy}>
              Acknowledge
            </Button>
            <Button size="sm" onClick={() => act("resolve")} loading={busy}>
              Resolve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => act("dismiss")} loading={busy}>
              Dismiss
            </Button>
            <Button size="sm" variant="ghost" onClick={() => act("reopen")} loading={busy}>
              Reopen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => act("annotate")}
              loading={busy}
              disabled={!note.trim()}
              title={!note.trim() ? "Enter a note to annotate" : "Add note"}
            >
              Add note
            </Button>
          </div>
        ) : null
      }
    >
      {!current ? (
        <LoadingPanel rows={4} />
      ) : (
        <div className="stack" style={{ gap: "var(--sp-4)" }}>
          {current.is_simulated && (
            <div className="sim-banner" role="note">
              <strong>SIMULATED</strong>
              <span>This incident was generated from synthetic observations.</span>
            </div>
          )}

          <div className="row wrap" style={{ gap: "var(--sp-2)" }}>
            <Badge tone={SEVERITY_META[current.severity].tone}>
              {SEVERITY_META[current.severity].label}
            </Badge>
            <Badge tone={EVENT_STATUS_META[current.status].tone}>
              {EVENT_STATUS_META[current.status].label}
            </Badge>
            <Badge tone={current.is_simulated ? "warn" : "info"}>
              {current.is_simulated ? "Simulated" : humanizeToken(current.provenance)}
            </Badge>
          </div>

          <dl className="kv">
            <dt>Rule</dt>
            <dd className="mono">
              {current.rule_id} · v{current.rule_version}
            </dd>
            <dt>Run</dt>
            <dd className="mono truncate">{current.run_id}</dd>
            <dt>First seen</dt>
            <dd>{formatDateTime(current.first_seen)}</dd>
            <dt>Last seen</dt>
            <dd>{formatDateTime(current.last_seen)}</dd>
            <dt>Tracks</dt>
            <dd className="mono">{current.track_ids.join(", ") || "-"}</dd>
            <dt>Evidence quality</dt>
            <dd>{current.evidence_quality ?? "-"}</dd>
          </dl>

          <div>
            <h3 className="field-label">Explanation</h3>
            <p>{current.explanation.human}</p>
            <details>
              <summary className="dim" style={{ fontSize: "var(--fs-sm)", cursor: "pointer" }}>
                Machine explanation ({current.explanation.generated_by})
              </summary>
              <pre className="code-block">
                {JSON.stringify(current.explanation.machine, null, 2)}
              </pre>
            </details>
          </div>

          <div>
            <h3 className="field-label">Evidence payload</h3>
            <pre className="code-block">{JSON.stringify(current.evidence, null, 2)}</pre>
          </div>

          <label className="field">
            <span className="field-label">Note (used with Add note)</span>
            <textarea
              className="input"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional context for the audit trail"
            />
          </label>

          <div>
            <h3 className="field-label">Audit trail</h3>
            {detail.loading && audit.length === 0 ? (
              <LoadingPanel rows={2} />
            ) : audit.length === 0 ? (
              <EmptyState title="No audit entries" />
            ) : (
              <div className="stack" style={{ gap: "var(--sp-2)" }}>
                {audit.map((entry) => (
                  <div key={entry.audit_id} className="row-between">
                    <div className="stack" style={{ gap: 0 }}>
                      <span>{humanizeToken(entry.action)}</span>
                      {entry.note && (
                        <span className="dim" style={{ fontSize: "var(--fs-xs)" }}>
                          {entry.note}
                        </span>
                      )}
                    </div>
                    <span className="dim mono" style={{ fontSize: "var(--fs-xs)" }}>
                      {entry.actor} · {formatDateTime(entry.timestamp)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
