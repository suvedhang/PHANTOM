import type { ReactNode } from "react";

import type { StatusTone } from "../lib/severity";

import "./components.css";

export interface BadgeProps {
  tone?: StatusTone;
  children: ReactNode;
  icon?: ReactNode;
  dot?: boolean;
  title?: string;
}

export function Badge({ tone = "neutral", children, icon, dot = false, title }: BadgeProps) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {dot && <span className="badge-dot" aria-hidden="true" />}
      {icon && <span className="badge-icon" aria-hidden="true">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}

/** Small monospace label for IDs and tokens. */
export function IdTag({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <code className="id-tag mono truncate" title={title}>
      {children}
    </code>
  );
}
