import type { ReactNode } from "react";

import "./components.css";

export interface StatTileProps {
  label: string;
  value: ReactNode;
  foot?: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
  small?: boolean;
}

export function StatTile({ label, value, foot, tone = "neutral", small = false }: StatTileProps) {
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      <span
        className={`stat-value ${small ? "stat-value-sm" : ""} tone-${tone}`}
        style={{ color: tone === "neutral" ? "var(--text-primary)" : undefined }}
      >
        {value}
      </span>
      {foot && <span className="stat-foot">{foot}</span>}
    </div>
  );
}
