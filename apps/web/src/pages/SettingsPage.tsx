import { useMemo, useState } from "react";

import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card, CardBody, CardHeader } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingPanel } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { useApi } from "../hooks/useApi";
import { useToast } from "../hooks/useToast";

type ConfigValue = string | number | boolean | null | ConfigValue[] | { [key: string]: ConfigValue };

function isSecretKey(key: string): boolean {
  return /(key|secret|token|password|passwd|credential)/i.test(key);
}

function renderValue(value: ConfigValue): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function SettingsPage() {
  const toast = useToast();
  const config = useApi(() => api.systemConfig(), []);
  const [revealed, setRevealed] = useState(false);

  const groups = useMemo(() => {
    const source = config.data?.config ?? {};
    const bucket: {
      General: Array<[string, ConfigValue]>;
      Pipeline: Array<[string, ConfigValue]>;
      Detector: Array<[string, ConfigValue]>;
      Transport: Array<[string, ConfigValue]>;
      Storage: Array<[string, ConfigValue]>;
      Other: Array<[string, ConfigValue]>;
    } = {
      General: [],
      Pipeline: [],
      Detector: [],
      Transport: [],
      Storage: [],
      Other: [],
    };
    for (const [key, value] of Object.entries(source) as Array<[string, ConfigValue]>) {
      if (key.startsWith("pipegen") || key.startsWith("pipeline")) bucket.Pipeline.push([key, value]);
      else if (key.startsWith("detector") || key.startsWith("model") || key.startsWith("inference"))
        bucket.Detector.push([key, value]);
      else if (key.startsWith("mqtt") || key.startsWith("ws") || key.startsWith("transport"))
        bucket.Transport.push([key, value]);
      else if (key.startsWith("output") || key.startsWith("evidence") || key.startsWith("export") || key.startsWith("db"))
        bucket.Storage.push([key, value]);
      else if (
        key.startsWith("app") ||
        key.startsWith("server") ||
        key.startsWith("api") ||
        key.startsWith("host") ||
        key.startsWith("port") ||
        key.startsWith("cors")
      )
        bucket.General.push([key, value]);
      else bucket.Other.push([key, value]);
    }
    return Object.entries(bucket).filter(([, entries]) => entries.length > 0);
  }, [config.data]);

  const copyAll = async () => {
    try {
      const entries = groups.flatMap(([, list]) => list);
      const text = entries
        .map(([key, value]) => `${key}=${isSecretKey(key) && !revealed ? "••••" : renderValue(value)}`)
        .join("\n");
      await navigator.clipboard.writeText(text);
      toast.ok("Configuration copied", "Redacted values are masked unless revealed.");
    } catch (err) {
      toast.error("Copy failed", err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="Settings"
        description="Effective runtime configuration as resolved by the API. Read-only; change values via environment variables."
        actions={
          <div className="row" style={{ gap: "var(--sp-2)" }}>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={revealed}
                onChange={(e) => setRevealed(e.target.checked)}
              />
              Reveal secrets
            </label>
            <Button variant="ghost" onClick={copyAll} disabled={!config.data}>
              Copy config
            </Button>
            <Button variant="ghost" onClick={config.reload} loading={config.refreshing}>
              Refresh
            </Button>
          </div>
        }
      />

      {config.error ? (
        <ErrorState error={config.error} onRetry={config.reload} />
      ) : config.loading && !config.data ? (
        <LoadingPanel rows={5} />
      ) : groups.length === 0 ? (
        <EmptyState title="No configuration" message="The API returned no configuration values." />
      ) : (
        groups.map(([groupName, entries]) => (
          <Card key={groupName}>
            <CardHeader title={groupName} subtitle={`${entries.length} value(s)`} />
            <CardBody>
              <dl className="kv">
                {entries.map(([key, value]) => {
                  const secret = isSecretKey(key);
                  const display =
                    secret && !revealed ? "••••••• (hidden)" : renderValue(value);
                  return (
                    <div key={key} className="kv-row">
                      <dt className="mono">{key}</dt>
                      <dd className={secret && !revealed ? "dim" : ""}>{display}</dd>
                    </div>
                  );
                })}
              </dl>
            </CardBody>
          </Card>
        ))
      )}

      <Card>
        <CardHeader title="Data provenance" />
        <CardBody>
          <div className="stack" style={{ gap: "var(--sp-2)" }}>
            <div className="row" style={{ gap: "var(--sp-2)" }}>
              <Badge tone="info">configured</Badge>
              <span className="dim">
                Regions, rules, and settings you create — never inferred from live data.
              </span>
            </div>
            <div className="row" style={{ gap: "var(--sp-2)" }}>
              <Badge tone="warn">simulated</Badge>
              <span className="dim">
                Observations produced by the deterministic mock adapter; labelled in the UI.
              </span>
            </div>
            <div className="row" style={{ gap: "var(--sp-2)" }}>
              <Badge tone="ok">observed</Badge>
              <span className="dim">
                Real detections from a verified PipeGen source (unavailable in demo mode).
              </span>
            </div>
            <div className="row" style={{ gap: "var(--sp-2)" }}>
              <Badge tone="neutral">derived</Badge>
              <span className="dim">Computed values such as durations and counts.</span>
            </div>
          </div>
        </CardBody>
      </Card>

      <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
        Configuration is served from the backend and reflects what the process actually loaded.
        Some values require a restart to change.
      </p>
    </div>
  );
}
