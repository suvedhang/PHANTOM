import { Badge } from "../components/Badge";
import { Card, CardBody, CardHeader } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { SCHEMA_VERSION } from "../api/types";

export function AboutPage() {
  return (
    <div className="stack" style={{ gap: "var(--sp-5)" }}>
      <PageHeader
        title="About PHANTOM"
        description="Scene-specific rule intelligence for physical AI operations."
      />

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Card>
          <CardHeader title="What this is" />
          <CardBody>
            <p>
              PHANTOM turns normalized computer-vision observations into deterministic,
              scene-specific rule violations and explainable incidents. Every event carries the
              rule version, geometry, and a machine-readable explanation that references only the
              observations that produced it.
            </p>
            <p className="dim" style={{ marginTop: 8 }}>
              Built for the Embedded SF CraftifAI Physical AI Hackathon, Track A. The system is
              designed to sit behind a PipeGen inference pipeline; in the absence of a verified
              PipeGen host it runs a clearly-labelled deterministic mock adapter so the full flow
              stays demonstrable.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="What this is not" />
          <CardBody>
            <ul className="plain-list">
              <li>Not a video player. Video playback requires a verified real source.</li>
              <li>
                Not a source of fabricated hardware telemetry. GPU, PipeGen versions, and model
                metrics are reported only when a real adapter verifies them; otherwise they are
                null.
              </li>
              <li>Not an autonomous action system. It produces explainable incidents, not commands.</li>
              <li>Not metrically accurate. Geometry is normalized image-space, not metres.</li>
            </ul>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Documentation" subtitle="Where to find the details" />
        <CardBody>
          <div className="stack" style={{ gap: "var(--sp-2)" }}>
            <DocRow
              label="Implementation plan & progress"
              path="docs/IMPLEMENTATION_PLAN.md"
            />
            <DocRow
              label="PipeGen integration contract"
              path="docs/PIPEGEN_INTEGRATION.md"
              note="What is known, assumed, and unverifiable about the real boundary."
            />
            <DocRow label="Event schema" path="docs/EVENT_SCHEMA.md" />
            <DocRow label="JSON Schemas" path="packages/contracts/schema/" />
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Data provenance" subtitle="Every value is tagged" />
        <CardBody>
          <div className="stack" style={{ gap: "var(--sp-3)" }}>
            <ProvenanceRow tone="ok" token="observed">
              Real detections from a verified source. Unavailable in demo mode.
            </ProvenanceRow>
            <ProvenanceRow tone="warn" token="simulated">
              Output of the deterministic mock adapter, always visibly labelled.
            </ProvenanceRow>
            <ProvenanceRow tone="info" token="configured">
              Regions, rules, and settings created by an operator.
            </ProvenanceRow>
            <ProvenanceRow tone="neutral" token="derived">
              Values computed from other data (durations, counts, correlations).
            </ProvenanceRow>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Event schema" />
        <CardBody>
          <dl className="kv">
            <dt>Schema version</dt>
            <dd className="mono">{SCHEMA_VERSION}</dd>
            <dt>Geometry</dt>
            <dd>Normalized image coordinates in [0,1], origin top-left</dd>
            <dt>Bounding box</dt>
            <dd className="mono">[x_min, y_min, x_max, y_max]</dd>
            <dt>Explanation</dt>
            <dd>Deterministic; generated from rule config and observations only</dd>
          </dl>
        </CardBody>
      </Card>

      <p className="dim" style={{ fontSize: "var(--fs-sm)" }}>
        This interface never invents live metrics. Any panel that could show real hardware data
        states explicitly when that data is unavailable.
      </p>
    </div>
  );
}

function DocRow({ label, path, note }: { label: string; path: string; note?: string }) {
  return (
    <div className="row-between">
      <div className="stack" style={{ gap: 0 }}>
        <span>{label}</span>
        {note && (
          <span className="dim" style={{ fontSize: "var(--fs-xs)" }}>
            {note}
          </span>
        )}
      </div>
      <code className="mono dim" style={{ fontSize: "var(--fs-xs)" }}>
        {path}
      </code>
    </div>
  );
}

function ProvenanceRow({
  tone,
  token,
  children,
}: {
  tone: "ok" | "warn" | "info" | "neutral";
  token: string;
  children: React.ReactNode;
}) {
  return (
    <div className="row" style={{ gap: "var(--sp-3)", alignItems: "flex-start" }}>
      <Badge tone={tone}>{token}</Badge>
      <span className="dim">{children}</span>
    </div>
  );
}
