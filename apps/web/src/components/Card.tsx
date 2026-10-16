import type { ReactNode } from "react";

import "./components.css";

export interface CardProps {
  children: ReactNode;
  className?: string;
  tone?: "default" | "danger" | "warn";
}

export function Card({ children, className, tone = "default" }: CardProps) {
  return <section className={`card card-${tone} ${className ?? ""}`}>{children}</section>;
}

export interface CardHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
}

export function CardHeader({ title, subtitle, actions, icon }: CardHeaderProps) {
  return (
    <div className="card-header">
      <div className="card-title-group">
        {icon && (
          <span className="card-title-icon" aria-hidden="true">
            {icon}
          </span>
        )}
        <div className="card-title-text">
          <h2 className="card-title">{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="card-actions">{actions}</div>}
    </div>
  );
}

export function CardBody({ children, pad = true }: { children: ReactNode; pad?: boolean }) {
  return <div className={pad ? "card-body" : "card-body card-body-flush"}>{children}</div>;
}
