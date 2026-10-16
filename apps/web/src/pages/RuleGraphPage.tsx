import { useMemo } from "react";

import { api } from "../api/client";
import type { RegionModel, RuleDefinition } from "../api/types";
import { Badge } from "../components/Badge";
import { Card, CardBody, CardHeader } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { useApi } from "../hooks/useApi";
import { useApp } from "../hooks/useApp";
import { pointInPolygon } from "../lib/geometry";

interface GraphNode {
  id: string;
  column: number;
  row: number;
  label: string;
  sublabel?: string;
  kind: "entity" | "region" | "rule";
  flagged?: boolean;
}

const COLUMN_X = [70, 350, 660] as const;
const ROW_H = 54;
const NODE_W = 200;
const NODE_H = 40;

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="row" style={{ gap: "var(--sp-2)" }}>
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: 3,
          background: color,
          display: "inline-block",
        }}
        aria-hidden="true"
      />
      <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-secondary)" }}>{label}</span>
    </span>
  );
}

export function RuleGraphPage() {
  const { latestFrame, eventsRevision } = useApp();
  const regions = useApi(() => api.listRegions(), []);
  const rules = useApi(() => api.listRules(), []);
  const activeEvents = useApi(
    () => api.listEvents({ status: "active", limit: 50 }),
    [eventsRevision],
    { pollMs: 8000 },
  );

  const flaggedRuleIds = useMemo(() => {
    const set = new Set<string>();
    for (const event of activeEvents.data?.items ?? []) set.add(event.rule_id);
    return set;
  }, [activeEvents.data]);

  const flaggedTrackIds = useMemo(() => {
    const set = new Set<string>();
    for (const event of activeEvents.data?.items ?? []) {
      for (const trackId of event.track_ids) set.add(trackId);
    }
    return set;
  }, [activeEvents.data]);

  const { nodes, edges, entityMembership } = useMemo(() => {
    const regionList: RegionModel[] = regions.data?.items ?? [];
    const ruleList: RuleDefinition[] = rules.data?.items ?? [];
    const entities = latestFrame?.entities ?? [];

    const nodes: GraphNode[] = [];
    const edges: Array<{ from: string; to: string }> = [];

    entities.forEach((entity, index) => {
      nodes.push({
        id: `entity:${entity.track_id ?? index}`,
        column: 0,
        row: index,
        label: entity.class_label,
        sublabel: entity.track_id ?? undefined,
        kind: "entity",
        flagged: entity.track_id ? flaggedTrackIds.has(entity.track_id) : false,
      });
    });

    regionList.forEach((region, index) => {
      nodes.push({
        id: `region:${region.region_id}`,
        column: 1,
        row: index,
        label: region.name,
        sublabel: region.region_id,
        kind: "region",
      });
    });

    ruleList.forEach((rule: RuleDefinition, index: number) => {
      const id = `rule:${rule.rule_id}`;
      nodes.push({
        id,
        column: 2,
        row: index,
        label: rule.name,
        sublabel: rule.type,
        kind: "rule",
        flagged: flaggedRuleIds.has(rule.rule_id),
      });
      if (
        rule.config.region_id &&
        (regions.data?.items ?? []).some((r) => r.region_id === rule.config.region_id)
      ) {
        edges.push({ from: `region:${rule.config.region_id}`, to: id });
      }
    });

    const membership = new Set<string>();
    for (const entity of latestFrame?.entities ?? []) {
      if (!entity.bbox || !entity.track_id) continue;
      const center = {
        x: (entity.bbox.x_min + entity.bbox.x_max) / 2,
        y: (entity.bbox.y_min + entity.bbox.y_max) / 2,
      };
      for (const region of regions.data?.items ?? []) {
        if (pointInPolygon(center, region.polygon)) {
          edges.push({ from: `entity:${entity.track_id}`, to: `region:${region.region_id}` });
          membership.add(`${entity.track_id}:${region.region_id}`);
        }
      }
    }

    return { nodes, edges, entityMembership: membership };
  }, [regions.data, rules.data, latestFrame, flaggedRuleIds, flaggedTrackIds]);

  const graphHeight =
    30 + Math.max(...nodes.map((n) => n.row + 1), 1) * ROW_H + 20;

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Rule Graph"
        description="How the current scene relates to configured regions and the rules that watch them."
        actions={<Badge tone="danger">Red = active incident</Badge>}
      />

      {latestFrame?.is_simulated && (
        <div className="sim-banner" role="note">
          <strong>SIMULATED SOURCE</strong>
          <span>Graph reflects synthetic tracks from the demo scenario.</span>
        </div>
      )}

      <Card>
        <CardHeader
          title="Scene graph"
          subtitle={`${nodes.length} nodes · ${edges.length} edges · ${entityMembership.size} active memberships`}
        />
        <CardBody pad={false}>
          {regions.loading || rules.loading ? (
            <div style={{ padding: "var(--sp-4)" }}>
              <LoadingPanel rows={4} />
            </div>
          ) : nodes.length === 0 ? (
            <div style={{ padding: "var(--sp-4)" }}>
              <EmptyState
                title="Nothing to graph yet"
                message="Start a simulated run and configure regions and rules to populate the graph."
              />
            </div>
          ) : (
            <div style={{ overflowX: "auto", padding: "var(--sp-4)" }}>
              <svg width={900} height={graphHeight} role="img" aria-label="Rule graph">
                {edges.map((edge, index) => {
                  const fromNode = nodes.find((n) => n.id === edge.from);
                  const toNode = nodes.find((n) => n.id === edge.to);
                  if (!fromNode || !toNode) return null;
                  const from = {
                    x: (COLUMN_X[fromNode.column] ?? 0) + NODE_W,
                    y: 30 + fromNode.row * ROW_H + NODE_H / 2,
                  };
                  const to = {
                    x: COLUMN_X[toNode.column] ?? 0,
                    y: 30 + toNode.row * ROW_H + NODE_H / 2,
                  };
                  const midX = (from.x + to.x) / 2;
                  return (
                    <path
                      key={`${edge.from}-${edge.to}-${index}`}
                      d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
                      fill="none"
                      stroke="var(--border-strong)"
                      strokeWidth="1.5"
                    />
                  );
                })}
                {nodes.map((node) => {
                  const x = COLUMN_X[node.column] ?? 0;
                  const y = 30 + node.row * ROW_H;
                  const color =
                    node.kind === "region"
                      ? "var(--accent)"
                      : node.kind === "rule"
                        ? node.flagged
                          ? "var(--danger)"
                          : "var(--ok)"
                        : node.flagged
                          ? "var(--warn)"
                          : "var(--text-secondary)";
                  return (
                    <g key={node.id}>
                      <rect
                        x={x}
                        y={y}
                        width={NODE_W}
                        height={NODE_H}
                        rx={8}
                        fill="var(--bg-panel-2)"
                        stroke={color}
                        strokeWidth="1.5"
                      />
                      <text
                        x={x + 12}
                        y={y + 17}
                        fill="var(--text-primary)"
                        fontSize="12"
                        fontWeight="600"
                      >
                        {node.label}
                      </text>
                      {node.sublabel && (
                        <text
                          x={x + 12}
                          y={y + 31}
                          fill="var(--text-muted)"
                          fontSize="10"
                          fontFamily="var(--font-mono)"
                        >
                          {node.sublabel}
                        </text>
                      )}
                    </g>
                  );
                })}
                <text x={COLUMN_X[0]} y={16} fill="var(--text-muted)" fontSize="11">
                  ENTITIES
                </text>
                <text x={COLUMN_X[1]} y={16} fill="var(--text-muted)" fontSize="11">
                  REGIONS
                </text>
                <text x={COLUMN_X[2]} y={16} fill="var(--text-muted)" fontSize="11">
                  RULES
                </text>
              </svg>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Legend" />
        <CardBody>
          <div className="row wrap" style={{ gap: "var(--sp-4)" }}>
            <LegendDot color="var(--text-secondary)" label="Entity (track)" />
            <LegendDot color="var(--accent)" label="Region" />
            <LegendDot color="var(--ok)" label="Rule (idle)" />
            <LegendDot color="var(--danger)" label="Rule (active incident)" />
            <span className="dim" style={{ fontSize: "var(--fs-sm)" }}>
              Edges connect entities to the regions that contain them and rules to their region.
            </span>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
