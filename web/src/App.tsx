import {
  BarChart3,
  Boxes,
  FileSliders,
  Gauge,
  PlayCircle
} from "lucide-react";
import { Suspense, lazy } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";

const ConfigBuilderPage = lazy(() => import("./pages/ConfigBuilderPage"));
const GeometryViewerPage = lazy(() => import("./pages/GeometryViewerPage"));
const ResultsDashboardPage = lazy(() => import("./pages/ResultsDashboardPage"));
const RunManagerPage = lazy(() => import("./pages/RunManagerPage"));

const navItems = [
  { to: "/config", label: "Config", icon: FileSliders },
  { to: "/runs", label: "Runs", icon: PlayCircle },
  { to: "/results/latest", label: "Results", icon: BarChart3 },
  { to: "/viewer/latest", label: "Viewer", icon: Boxes }
];

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">
            <Gauge size={20} strokeWidth={2.2} />
          </div>
          <div>
            <h1>FanC(fd)</h1>
            <p>CFD workbench</p>
          </div>
        </div>
        <nav className="side-nav" aria-label="Primary">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to}>
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main-surface">
        <Suspense fallback={<div className="route-loading">Loading workbench...</div>}>
          <Routes>
            <Route path="/" element={<Navigate to="/config" replace />} />
            <Route path="/config" element={<ConfigBuilderPage />} />
            <Route path="/config/:configId" element={<ConfigBuilderPage />} />
            <Route path="/runs" element={<RunManagerPage />} />
            <Route path="/runs/:jobId" element={<RunManagerPage />} />
            <Route path="/results/:runId" element={<ResultsDashboardPage />} />
            <Route path="/viewer/:runId" element={<GeometryViewerPage />} />
            <Route path="/optimize/:jobId" element={<ResultsDashboardPage optimizeMode />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}
