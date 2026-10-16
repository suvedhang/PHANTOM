import { Link, Route, Routes } from "react-router-dom";

import { EmptyState } from "./components/EmptyState";
import { AppShell } from "./layout/AppShell";
import { AboutPage } from "./pages/AboutPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { EventsPage } from "./pages/EventsPage";
import { EvidencePage } from "./pages/EvidencePage";
import { LiveScenePage } from "./pages/LiveScenePage";
import { OverviewPage } from "./pages/OverviewPage";
import { PipelinePage } from "./pages/PipelinePage";
import { RegionsPage } from "./pages/RegionsPage";
import { RuleGraphPage } from "./pages/RuleGraphPage";
import { RulesPage } from "./pages/RulesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SystemHealthPage } from "./pages/SystemHealthPage";

function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      message="The page you requested does not exist."
      action={<Link className="btn btn-secondary btn-sm" to="/">Back to overview</Link>}
    />
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="live" element={<LiveScenePage />} />
        <Route path="graph" element={<RuleGraphPage />} />
        <Route path="events" element={<EventsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="rules" element={<RulesPage />} />
        <Route path="regions" element={<RegionsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="pipeline" element={<PipelinePage />} />
        <Route path="health" element={<SystemHealthPage />} />
        <Route path="evidence" element={<EvidencePage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
