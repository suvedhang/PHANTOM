import { useState } from "react";

import { api } from "../api/client";
import type { EvidenceArtifact } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { Dialog } from "../components/Dialog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { StatTile } from "../components/StatTile";
import { DataTable, type Column } from "../components/Table";
import { useApi } from "../hooks/useApi";
import { useToast } from "../hooks/useToast";
import { formatDateTime } from "../lib/format";
import { EVIDENCE_STATUS_META } from "../lib/severity";

export function EvidencePage() {
  const toast = useToast();
  const evidence = useApi(() => api.evidenceStatus(), []);
  const [editing, setEditing] = useState<EvidenceArtifact | null>(null);
  const [draftPath, setDraftPath] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const verify = async (artifact: EvidenceArtifact, status: "verified" | "invalid") => {
    try {
      await api.verifyArtifact(artifact.artifact_id, { status });
      toast.ok(`Artifact ${status}`, artifact.label);
      evidence.reload();
    } catch (err) {
      toast.error("Verification failed", err instanceof Error ? err.message : String(err));
    }
  };

  const openEditArtifact = (a: EvidenceArtifact) => {
    setEditing(a);
    setDraftPath(a.path);
    setDraftNotes(a.notes);
  };

  const saveArtifact = async () => {
    if (!editing) return;
    setBusy(true);
    try {
      await api.updateArtifact(editing.artifact_id, { path: draftPath, notes: draftNotes });
      toast.ok("Artifact updated", editing.label);
      setEditing(null);
      evidence.reload();
    } catch (err) {
      toast.error("Could not update artifact", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<EvidenceArtifact>[] = [
    {
      key: "label",
      header: "Artifact",
      sortable: true,
      render: (a) => (
        <div className="stack" style={{ gap: 0 }}>
          <strong>{a.label}</strong>
          <span className="dim mono" style={{ fontSize: "var(--fs-xs)" }}>
            {a.type}
            {a.required ? " · required" : ""}
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (a) => (
        <Badge tone={EVIDENCE_STATUS_META[a.status].tone}>
          {EVIDENCE_STATUS_META[a.status].label}
        </Badge>
      ),
    },
    {
      key: "path",
      header: "Path",
      render: (a) =>
        a.path ? (
          <span className="mono truncate" title={a.path}>
            {a.path}
          </span>
        ) : (
          <span className="dim">not set</span>
        ),
    },
    {
      key: "verified_at",
      header: "Verified",
      sortable: true,
      sortValue: (a) => a.verified_at ?? "",
      render: (a) => <span className="dim">{a.verified_at ? formatDateTime(a.verified_at) : "-"}</span>,
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (a) => (
        <div className="row" style={{ gap: "var(--sp-2)", justifyContent: "flex-end" }}>
          <Button size="sm" variant="ghost" onClick={() => openEditArtifact(a)}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => verify(a, "verified")}>
            Verify
          </Button>
          <Button size="sm" variant="ghost" onClick={() => verify(a, "invalid")}>
            Invalidate
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Evidence"
        description="Hackathon submission artifacts and their verification state. Status is only ever set by an explicit reviewer action."
        actions={
          <Button variant="ghost" onClick={evidence.reload} loading={evidence.refreshing}>
            Refresh
          </Button>
        }
      />

      {evidence.error ? (
        <ErrorState error={evidence.error} onRetry={evidence.reload} />
      ) : evidence.loading && !evidence.data ? (
        <LoadingPanel rows={5} />
      ) : !evidence.data ? (
        <EmptyState title="No evidence data" message="Evidence status is unavailable." />
      ) : (
        <>
          <div className="grid stat-grid">
            <StatTile
              label="Required verified"
              value={`${evidence.data.required_verified} / ${evidence.data.required_total}`}
              tone={evidence.data.complete ? "ok" : "warn"}
            />
            <StatTile
              label="Missing required"
              value={evidence.data.missing_required}
              tone={evidence.data.missing_required > 0 ? "danger" : "neutral"}
            />
            <StatTile label="Total artifacts" value={evidence.data.items.length} />
            <StatTile
              label="Complete"
              value={
                <Badge tone={evidence.data.complete ? "ok" : "warn"}>
                  {evidence.data.complete ? "Yes" : "No"}
                </Badge>
              }
            />
          </div>

          <Card>
            <CardHeader title="Evidence checklist" subtitle={evidence.data.note} />
            <CardBody>
              <DataTable
                columns={columns}
                rows={evidence.data.items}
                rowKey={(a) => a.artifact_id}
                caption="Evidence artifacts"
                empty={<EmptyState title="No artifacts" message="No evidence artifacts are registered." />}
              />
            </CardBody>
          </Card>
        </>
      )}

      <Dialog
        open={editing !== null}
        title={`Edit artifact · ${editing?.label ?? ""}`}
        onClose={() => setEditing(null)}
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={saveArtifact} loading={busy}>
              Save
            </Button>
          </>
        }
      >
        <div className="stack" style={{ gap: "var(--sp-4)" }}>
          <label className="field">
            <span className="field-label">Path</span>
            <input
              className="input"
              value={draftPath}
              onChange={(e) => setDraftPath(e.target.value)}
              placeholder="Relative path to the artifact"
            />
          </label>
          <label className="field">
            <span className="field-label">Notes</span>
            <textarea
              className="input"
              rows={3}
              value={draftNotes}
              onChange={(e) => setDraftNotes(e.target.value)}
            />
          </label>
          <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
            Editing the path marks the artifact as requiring re-verification. Downloading and
            hashing happens on the backend; the browser never fabricates checksums.
          </p>
        </div>
      </Dialog>
    </div>
  );
}
