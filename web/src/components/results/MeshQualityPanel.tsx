import { ShieldCheck } from "lucide-react";
import type { ResultsResponse } from "../../types/api";

interface MeshQualityPanelProps {
  results?: ResultsResponse;
}

export default function MeshQualityPanel({ results }: MeshQualityPanelProps) {
  const mesh = results?.mesh ?? {};
  return (
    <section className="mesh-panel">
      <div className="section-heading row">
        <div>
          <h2>Mesh quality</h2>
          <span>{typeof mesh.n_cells === "number" ? `${mesh.n_cells.toLocaleString()} cells` : "No cell count"}</span>
        </div>
        <ShieldCheck size={18} />
      </div>
      <div className="gauge-row">
        <Gauge
          label="Max non-ortho"
          value={numeric(mesh.max_non_ortho)}
          suffix=" deg"
          thresholds={[50, 65]}
        />
        <Gauge
          label="Max skewness"
          value={numeric(mesh.max_skewness)}
          suffix=""
          thresholds={[2, 4]}
        />
      </div>
    </section>
  );
}

function Gauge({
  label,
  value,
  suffix,
  thresholds
}: {
  label: string;
  value: number | null;
  suffix: string;
  thresholds: [number, number];
}) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, (value / thresholds[1]) * 100));
  const tone = value === null ? "neutral" : value < thresholds[0] ? "teal" : value < thresholds[1] ? "amber" : "red";
  return (
    <div className={`quality-gauge ${tone}`}>
      <div className="gauge-track">
        <span style={{ width: `${pct}%` }} />
      </div>
      <div>
        <strong>{value === null ? "No data" : `${value.toFixed(2)}${suffix}`}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function numeric(value: unknown) {
  return typeof value === "number" ? value : null;
}
