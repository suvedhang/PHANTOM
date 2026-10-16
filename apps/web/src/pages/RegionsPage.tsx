import { useCallback, useMemo, useState } from "react";

import { api } from "../api/client";
import type { Point, RegionModel } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { ConfirmDialog, Dialog } from "../components/Dialog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/Table";
import { useApi } from "../hooks/useApi";
import { useToast } from "../hooks/useToast";

interface DraftRegion {
  region_id: string | null;
  name: string;
  points: Point[];
  enabled: boolean;
}

const EMPTY_DRAFT: DraftRegion = { region_id: null, name: "", points: [], enabled: true };

function PolygonEditor({
  points,
  onChange,
}: {
  points: Point[];
  onChange: (points: Point[]) => void;
}) {
  const addPoint = useCallback(
    (event: React.MouseEvent<SVGSVGElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
      const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
      onChange([...points, { x, y }]);
    },
    [points, onChange],
  );

  const polygonPoints = useMemo(
    () => points.map((p) => `${p.x},${p.y}`).join(" "),
    [points],
  );

  return (
    <div className="stack" style={{ gap: "var(--sp-3)" }}>
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="region-editor"
        onClick={addPoint}
        role="img"
        aria-label="Region polygon editor. Click to add vertices."
      >
        {[0.25, 0.5, 0.75].map((f) => (
          <g key={f}>
            <line x1={f} y1={0} x2={f} y2={1} className="editor-grid" vectorEffect="non-scaling-stroke" />
            <line x1={0} y1={f} x2={1} y2={f} className="editor-grid" vectorEffect="non-scaling-stroke" />
          </g>
        ))}
        {points.length >= 2 && (
          <polygon
            points={polygonPoints}
            className="overlay-region"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {points.map((p, index) => (
          <circle
            key={`${p.x}-${p.y}-${index}`}
            cx={p.x}
            cy={p.y}
            r={0.012}
            className="editor-vertex"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div className="row-between">
        <span className="dim" style={{ fontSize: "var(--fs-sm)" }}>
          {points.length} vertex{points.length === 1 ? "" : "es"} · click the canvas to add.
          Coordinates are normalized [0,1].
        </span>
        <div className="row" style={{ gap: "var(--sp-2)" }}>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onChange(points.slice(0, -1))}
            disabled={points.length === 0}
          >
            Undo vertex
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onChange([])}
            disabled={points.length === 0}
          >
            Clear
          </Button>
        </div>
      </div>
    </div>
  );
}

export function RegionsPage() {
  const toast = useToast();
  const regions = useApi(() => api.listRegions(), []);
  const [draft, setDraft] = useState<DraftRegion | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<RegionModel | null>(null);

  const openCreate = () => setDraft({ ...EMPTY_DRAFT });
  const openEdit = (region: RegionModel) =>
    setDraft({
      region_id: region.region_id,
      name: region.name,
      points: [...region.polygon.points],
      enabled: region.enabled,
    });

  const save = async () => {
    if (!draft) return;
    if (!draft.name.trim()) {
      toast.error("Name required", "Give the region a descriptive name.");
      return;
    }
    if (draft.points.length < 3) {
      toast.error("Not enough vertices", "A region needs at least 3 points.");
      return;
    }
    setBusy(true);
    try {
      const body = {
        name: draft.name.trim(),
        polygon: { points: draft.points },
        enabled: draft.enabled,
      };
      if (draft.region_id) {
        await api.updateRegion(draft.region_id, body);
        toast.ok("Region updated", draft.name);
      } else {
        await api.createRegion(body);
        toast.ok("Region created", draft.name);
      }
      setDraft(null);
      regions.reload();
    } catch (err) {
      toast.error("Could not save region", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      await api.deleteRegion(pendingDelete.region_id);
      toast.ok("Region deleted", pendingDelete.name);
      setPendingDelete(null);
      regions.reload();
    } catch (err) {
      toast.error("Could not delete region", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<RegionModel>[] = [
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (r) => <strong>{r.name}</strong>,
    },
    {
      key: "region_id",
      header: "ID",
      render: (r) => <span className="mono dim">{r.region_id}</span>,
    },
    {
      key: "vertices",
      header: "Vertices",
      align: "right",
      render: (r) => r.polygon.points.length,
    },
    {
      key: "enabled",
      header: "State",
      render: (r) => (
        <Badge tone={r.enabled ? "ok" : "neutral"}>{r.enabled ? "Enabled" : "Disabled"}</Badge>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (r) => (
        <div className="row" style={{ gap: "var(--sp-2)", justifyContent: "flex-end" }}>
          <Button size="sm" variant="ghost" onClick={() => openEdit(r)}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPendingDelete(r)}>
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Regions"
        description="Named polygons in normalized image space used by region-aware rules."
        actions={
          <Button variant="primary" onClick={openCreate}>
            New region
          </Button>
        }
      />

      <Card>
        <CardHeader
          title="Configured regions"
          subtitle={`${regions.data?.items.length ?? 0} region(s)`}
          actions={
            <Button size="sm" variant="ghost" onClick={regions.reload} loading={regions.refreshing}>
              Refresh
            </Button>
          }
        />
        <CardBody>
          {regions.error ? (
            <ErrorState error={regions.error} onRetry={regions.reload} />
          ) : regions.loading && !regions.data ? (
            <LoadingPanel rows={4} />
          ) : (
            <DataTable
              columns={columns}
              rows={regions.data?.items ?? []}
              rowKey={(r) => r.region_id}
              caption="Configured regions"
              empty={
                <EmptyState
                  title="No regions yet"
                  message="Create a region to attach region-entry, dwell, and count rules."
                  action={<Button onClick={openCreate}>New region</Button>}
                />
              }
            />
          )}
        </CardBody>
      </Card>

      <Dialog
        open={draft !== null}
        title={draft?.region_id ? "Edit region" : "New region"}
        onClose={() => setDraft(null)}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={save} loading={busy}>
              {draft?.region_id ? "Save changes" : "Create region"}
            </Button>
          </>
        }
      >
        {draft && (
          <div className="stack" style={{ gap: "var(--sp-4)" }}>
            <label className="field">
              <span className="field-label">Name</span>
              <input
                className="input"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="e.g. Loading dock"
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
              />
              Enabled (evaluated by rules)
            </label>
            <PolygonEditor
              points={draft.points}
              onChange={(points) => setDraft({ ...draft, points })}
            />
          </div>
        )}
      </Dialog>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete region"
        destructive
        busy={busy}
        confirmLabel="Delete"
        message={
          <>
            Delete <strong>{pendingDelete?.name}</strong>? Rules referencing this region will no
            longer evaluate against it.
          </>
        }
        onConfirm={confirmDelete}
        onClose={() => setPendingDelete(null)}
      />

      <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
        Region geometry is stored as normalized image coordinates and is always explicitly
        configured, never inferred from live data. Region data created in demo mode is tagged as
        configured, not observed.
      </p>
    </div>
  );
}
