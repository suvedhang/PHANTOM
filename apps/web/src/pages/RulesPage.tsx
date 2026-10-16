import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { RegionModel, RuleConfig, RuleDefinition, RuleType, Severity } from "../api/types";
import { SUPPORTED_RULE_TYPES } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { Dialog } from "../components/Dialog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/Table";
import { useApi } from "../hooks/useApi";
import { useToast } from "../hooks/useToast";
import { formatDateTime, humanizeToken } from "../lib/format";
import { SEVERITY_META } from "../lib/severity";

const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];

const REGION_TYPES: RuleType[] = ["region_entry", "region_exit", "dwell_time", "wrong_way"];

function defaultConfig(): RuleConfig {
  return {
    region_id: null,
    class_filter: [],
    dwell_seconds: null,
    count_threshold: null,
    sustain_seconds: null,
    allowed_direction_deg: null,
    min_displacement: null,
    min_confidence: null,
    cooldown_seconds: 30,
    dedup_seconds: 10,
  };
}

interface DraftRule {
  rule_id: string | null;
  name: string;
  description: string;
  type: RuleType;
  severity: Severity;
  enabled: boolean;
  config: RuleConfig;
}

function RuleConfigEditor({
  type,
  config,
  regions,
  onChange,
}: {
  type: RuleType;
  config: RuleConfig;
  regions: RegionModel[];
  onChange: (config: RuleConfig) => void;
}) {
  const set = (patch: Partial<RuleConfig>) => onChange({ ...config, ...patch });
  const numberValue = (v: number | null) => (v === null ? "" : String(v));
  const parseNum = (value: string): number | null => {
    if (value.trim() === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };

  return (
    <div className="form-grid">
      {REGION_TYPES.includes(type) && (
        <label className="field">
          <span className="field-label">Region</span>
          <select
            className="input"
            value={config.region_id ?? ""}
            onChange={(e) => set({ region_id: e.target.value || null })}
          >
            <option value="">(none selected)</option>
            {regions.map((r) => (
              <option key={r.region_id} value={r.region_id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="field">
        <span className="field-label">Class filter (comma-separated, blank = all)</span>
        <input
          className="input"
          value={config.class_filter.join(", ")}
          onChange={(e) =>
            set({
              class_filter: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          placeholder="person, forklift"
        />
      </label>

      {type === "dwell_time" && (
        <label className="field">
          <span className="field-label">Dwell threshold (seconds)</span>
          <input
            className="input"
            type="number"
            min={0}
            value={numberValue(config.dwell_seconds)}
            onChange={(e) => set({ dwell_seconds: parseNum(e.target.value) })}
          />
        </label>
      )}

      {type === "wrong_way" && (
        <>
          <label className="field">
            <span className="field-label">Expected direction (degrees)</span>
            <input
              className="input"
              type="number"
              value={numberValue(config.allowed_direction_deg)}
              onChange={(e) => set({ allowed_direction_deg: parseNum(e.target.value) })}
            />
          </label>
          <label className="field">
            <span className="field-label">Min displacement (normalized)</span>
            <input
              className="input"
              type="number"
              step="0.01"
              min={0}
              value={numberValue(config.min_displacement)}
              onChange={(e) => set({ min_displacement: parseNum(e.target.value) })}
            />
          </label>
        </>
      )}

      {type === "count_threshold" && (
        <>
          <label className="field">
            <span className="field-label">Count threshold</span>
            <input
              className="input"
              type="number"
              min={0}
              value={numberValue(config.count_threshold)}
              onChange={(e) => set({ count_threshold: parseNum(e.target.value) })}
            />
          </label>
          <label className="field">
            <span className="field-label">Sustain (seconds)</span>
            <input
              className="input"
              type="number"
              min={0}
              value={numberValue(config.sustain_seconds)}
              onChange={(e) => set({ sustain_seconds: parseNum(e.target.value) })}
            />
          </label>
        </>
      )}

      <label className="field">
        <span className="field-label">Min confidence (0-1, optional)</span>
        <input
          className="input"
          type="number"
          step="0.01"
          min={0}
          max={1}
          value={numberValue(config.min_confidence)}
          onChange={(e) => set({ min_confidence: parseNum(e.target.value) })}
        />
      </label>

      <label className="field">
        <span className="field-label">Cooldown (seconds)</span>
        <input
          className="input"
          type="number"
          min={0}
          value={numberValue(config.cooldown_seconds)}
          onChange={(e) => set({ cooldown_seconds: parseNum(e.target.value) ?? 0 })}
        />
      </label>

      <label className="field">
        <span className="field-label">Dedup window (seconds)</span>
        <input
          className="input"
          type="number"
          min={0}
          value={numberValue(config.dedup_seconds)}
          onChange={(e) => set({ dedup_seconds: parseNum(e.target.value) ?? 0 })}
        />
      </label>
    </div>
  );
}

export function RulesPage() {
  const toast = useToast();
  const rules = useApi(() => api.listRules(), []);
  const regions = useApi(() => api.listRegions(), []);
  const [draft, setDraft] = useState<DraftRule | null>(null);
  const [busy, setBusy] = useState(false);
  const [versionsFor, setVersionsFor] = useState<RuleDefinition | null>(null);
  const [testFor, setTestFor] = useState<RuleDefinition | null>(null);
  const [testResult, setTestResult] = useState<{
    would_trigger_count: number;
    evaluated_observations: number;
    note: string;
  } | null>(null);
  const [testBusy, setTestBusy] = useState(false);

  const regionNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const region of regions.data?.items ?? []) map.set(region.region_id, region.name);
    return map;
  }, [regions.data]);

  const openCreate = () =>
    setDraft({
      rule_id: null,
      name: "",
      description: "",
      type: "region_entry",
      severity: "medium",
      enabled: true,
      config: defaultConfig(),
    });

  const openEdit = (rule: RuleDefinition) =>
    setDraft({
      rule_id: rule.rule_id,
      name: rule.name,
      description: rule.description,
      type: rule.type,
      severity: rule.severity,
      enabled: rule.enabled,
      config: { ...rule.config },
    });

  const save = async () => {
    if (!draft) return;
    if (!draft.name.trim()) {
      toast.error("Name required", "Give the rule a descriptive name.");
      return;
    }
    setBusy(true);
    try {
      if (draft.rule_id) {
        await api.updateRule(draft.rule_id, {
          name: draft.name.trim(),
          description: draft.description,
          config: draft.config,
          severity: draft.severity,
          enabled: draft.enabled,
        });
        toast.ok("Rule updated", draft.name);
      } else {
        await api.createRule({
          name: draft.name.trim(),
          description: draft.description,
          type: draft.type,
          config: draft.config,
          severity: draft.severity,
          enabled: draft.enabled,
        });
        toast.ok("Rule created", draft.name);
      }
      setDraft(null);
      rules.reload();
    } catch (err) {
      toast.error("Could not save rule", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleEnabled = async (rule: RuleDefinition) => {
    try {
      await api.updateRule(rule.rule_id, { enabled: !rule.enabled });
      toast.ok(
        rule.enabled ? "Rule disabled" : "Rule enabled",
        rule.name,
      );
      rules.reload();
    } catch (err) {
      toast.error("Could not update rule", err instanceof Error ? err.message : String(err));
    }
  };

  const runSampleTest = async (rule: RuleDefinition) => {
    setTestFor(rule);
    setTestResult(null);
    setTestBusy(true);
    try {
      const result = await api.sampleTestRule(rule.rule_id);
      setTestResult({
        would_trigger_count: result.would_trigger_count,
        evaluated_observations: result.evaluated_observations,
        note: result.note,
      });
    } catch (err) {
      toast.error("Sample test failed", err instanceof Error ? err.message : String(err));
      setTestFor(null);
    } finally {
      setTestBusy(false);
    }
  };

  const columns: Column<RuleDefinition>[] = [
    {
      key: "name",
      header: "Rule",
      sortable: true,
      render: (r) => (
        <div className="stack" style={{ gap: 0 }}>
          <strong>{r.name}</strong>
          <span className="dim" style={{ fontSize: "var(--fs-xs)" }}>
            {r.rule_id}
          </span>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (r) => humanizeToken(r.type),
    },
    {
      key: "region",
      header: "Region",
      render: (r) => (r.config.region_id ? regionNames.get(r.config.region_id) ?? r.config.region_id : "-"),
    },
    {
      key: "severity",
      header: "Severity",
      sortable: true,
      sortValue: (r) => SEVERITIES.indexOf(r.severity),
      render: (r) => (
        <Badge tone={SEVERITY_META[r.severity].tone}>{SEVERITY_META[r.severity].label}</Badge>
      ),
    },
    {
      key: "enabled",
      header: "State",
      render: (r) => (
        <Badge tone={r.enabled ? "ok" : "neutral"}>{r.enabled ? "Enabled" : "Disabled"}</Badge>
      ),
    },
    {
      key: "updated",
      header: "Updated",
      sortable: true,
      sortValue: (r) => r.updated_at,
      render: (r) => <span className="dim">{formatDateTime(r.updated_at)}</span>,
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
          <Button size="sm" variant="ghost" onClick={() => runSampleTest(r)}>
            Test
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setVersionsFor(r)}>
            Versions
          </Button>
          <Button size="sm" variant="ghost" onClick={() => toggleEnabled(r)}>
            {r.enabled ? "Disable" : "Enable"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Rules"
        description="Deterministic rule definitions evaluated against normalized observations."
        actions={
          <Button variant="primary" onClick={openCreate}>
            New rule
          </Button>
        }
      />

      <Card>
        <CardHeader
          title="Rule definitions"
          subtitle={`${rules.data?.items.length ?? 0} rule(s)`}
          actions={
            <Button size="sm" variant="ghost" onClick={rules.reload} loading={rules.refreshing}>
              Refresh
            </Button>
          }
        />
        <CardBody>
          {rules.error ? (
            <ErrorState error={rules.error} onRetry={rules.reload} />
          ) : rules.loading && !rules.data ? (
            <LoadingPanel rows={5} />
          ) : (
            <DataTable
              columns={columns}
              rows={rules.data?.items ?? []}
              rowKey={(r) => r.rule_id}
              caption="Rule definitions"
              empty={
                <EmptyState
                  title="No rules yet"
                  message="Create a rule to start detecting scene-specific conditions."
                  action={<Button onClick={openCreate}>New rule</Button>}
                />
              }
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Engine scope" subtitle="Types the deterministic engine evaluates today" />
        <CardBody>
          <div className="row wrap" style={{ gap: "var(--sp-2)" }}>
            {SUPPORTED_RULE_TYPES.map((type) => (
              <Badge key={type} tone="info">
                {humanizeToken(type)}
              </Badge>
            ))}
          </div>
          <p className="dim" style={{ fontSize: "var(--fs-sm)", marginTop: 10 }}>
            Rule creation is restricted to these types. Unsupported rule types are listed in the
            API contract but are not evaluated by the engine.
          </p>
        </CardBody>
      </Card>

      <Dialog
        open={draft !== null}
        title={draft?.rule_id ? "Edit rule" : "New rule"}
        onClose={() => setDraft(null)}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={save} loading={busy}>
              {draft?.rule_id ? "Save changes" : "Create rule"}
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
              />
            </label>
            <label className="field">
              <span className="field-label">Description</span>
              <textarea
                className="input"
                rows={2}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </label>
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Type</span>
                <select
                  className="input"
                  value={draft.type}
                  disabled={draft.rule_id !== null}
                  onChange={(e) => setDraft({ ...draft, type: e.target.value as RuleType })}
                >
                  {SUPPORTED_RULE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {humanizeToken(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Severity</span>
                <select
                  className="input"
                  value={draft.severity}
                  onChange={(e) => setDraft({ ...draft, severity: e.target.value as Severity })}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>
                      {SEVERITY_META[s].label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
              />
              Enabled
            </label>
            <RuleConfigEditor
              type={draft.type}
              config={draft.config}
              regions={regions.data?.items ?? []}
              onChange={(config) => setDraft({ ...draft, config })}
            />
          </div>
        )}
      </Dialog>

      <Dialog
        open={versionsFor !== null}
        title={`Versions · ${versionsFor?.name ?? ""}`}
        onClose={() => setVersionsFor(null)}
        size="lg"
      >
        {versionsFor && <RuleVersions ruleId={versionsFor.rule_id} />}
      </Dialog>

      <Dialog
        open={testFor !== null}
        title={`Sample test · ${testFor?.name ?? ""}`}
        onClose={() => {
          setTestFor(null);
          setTestResult(null);
        }}
        size="md"
        footer={
          <Button variant="ghost" onClick={() => setTestFor(null)}>
            Close
          </Button>
        }
      >
        {testBusy ? (
          <LoadingPanel rows={2} />
        ) : testResult ? (
          <div className="stack" style={{ gap: "var(--sp-3)" }}>
            <div className="row" style={{ gap: "var(--sp-5)" }}>
              <div>
                <div className="field-label">Observations evaluated</div>
                <div className="mono">{testResult.evaluated_observations}</div>
              </div>
              <div>
                <div className="field-label">Would trigger</div>
                <div className="mono">{testResult.would_trigger_count}</div>
              </div>
            </div>
            <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
              {testResult.note}
            </p>
            <div className="sim-banner" role="note">
              <strong>DRY RUN</strong>
              <span>No events are created. This evaluates the bundled sample against the rule only.</span>
            </div>
          </div>
        ) : (
          <EmptyState title="No result" message="The sample test returned nothing." />
        )}
      </Dialog>
    </div>
  );
}

function RuleVersions({ ruleId }: { ruleId: string }) {
  const versions = useApi(() => api.listRuleVersions(ruleId), [ruleId]);
  if (versions.loading && !versions.data) return <LoadingPanel rows={3} />;
  if (versions.error) return <ErrorState error={versions.error} onRetry={versions.reload} />;
  const items = versions.data?.items ?? [];
  if (items.length === 0) {
    return <EmptyState title="No versions" message="No historical versions recorded for this rule." />;
  }
  return (
    <div className="stack" style={{ gap: "var(--sp-3)" }}>
      {items
        .slice()
        .reverse()
        .map((entry) => (
          <div key={entry.version} className="row-between">
            <div className="stack" style={{ gap: 0 }}>
              <strong>v{entry.version}</strong>
              <span className="dim" style={{ fontSize: "var(--fs-xs)" }}>
                {entry.snapshot.name} · {humanizeToken(entry.snapshot.type)} ·{" "}
                {SEVERITY_META[entry.snapshot.severity].label}
              </span>
            </div>
            <span className="dim mono" style={{ fontSize: "var(--fs-xs)" }}>
              {formatDateTime(entry.created_at)}
            </span>
          </div>
        ))}
    </div>
  );
}
