import { NavLink, Outlet } from "react-router-dom";

import { useApp } from "../hooks/useApp";
import { RunControl } from "./RunControl";
import { StatusStrip } from "./StatusStrip";

import "./layout.css";

interface NavItem {
  to: string;
  label: string;
}

const NAV_GROUPS: Array<{ heading: string; items: NavItem[] }> = [
  {
    heading: "Operations",
    items: [
      { to: "/", label: "Overview" },
      { to: "/live", label: "Live Scene" },
      { to: "/graph", label: "Rule Graph" },
    ],
  },
  {
    heading: "Incidents",
    items: [
      { to: "/events", label: "Events" },
      { to: "/analytics", label: "Analytics" },
    ],
  },
  {
    heading: "Configuration",
    items: [
      { to: "/rules", label: "Rules" },
      { to: "/regions", label: "Regions" },
      { to: "/settings", label: "Settings" },
    ],
  },
  {
    heading: "System",
    items: [
      { to: "/pipeline", label: "Pipeline" },
      { to: "/health", label: "System Health" },
    ],
  },
  {
    heading: "Project",
    items: [
      { to: "/evidence", label: "Evidence" },
      { to: "/about", label: "About" },
    ],
  },
];

export function AppShell() {
  const { status, socketState } = useApp();
  const demoMode = status?.demo_mode ?? false;
  const simulated = status?.pipeline.is_simulated ?? false;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◈
          </span>
          <span className="brand-text">
            <strong>PHANTOM</strong>
            <span className="brand-sub">Visual Scene Intelligence</span>
          </span>
        </div>
        <nav className="nav" aria-label="Primary">
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.heading}>
              <span className="nav-heading">{group.heading}</span>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={`status-chip tone-${socketState === "open" ? "ok" : "warn"}`}>
            <span
              className={`status-dot ${socketState === "open" ? "status-dot-pulse" : ""}`}
              aria-hidden="true"
            />
            {socketState === "open" ? "Live transport" : "Transport offline"}
          </span>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            {(demoMode || simulated) && (
              <span className="demo-chip" role="note">
                {simulated ? "SIMULATED SOURCE" : "DEMO MODE"}
              </span>
            )}
          </div>
          <RunControl />
        </header>
        <StatusStrip />
        <main className="content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
