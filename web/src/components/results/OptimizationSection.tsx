import { useEffect, useMemo, useRef } from "react";
import type { OptimizationResponse } from "../../types/api";

interface OptimizationSectionProps {
  optimization?: OptimizationResponse;
}

export default function OptimizationSection({ optimization }: OptimizationSectionProps) {
  const rows = optimization?.leaderboard ?? [];
  return (
    <section className="optimization-section">
      <div className="section-heading row">
        <div>
          <h2>Optimization</h2>
          <span>{rows.length} leaderboard row(s)</span>
        </div>
      </div>
      <div className="optimization-grid">
        <div className="table-panel">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Trial</th>
                <th>Score</th>
                <th>Efficiency</th>
                <th>Pressure</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.trial_id}-${index}`}>
                  <td>{row.rank ?? index + 1}</td>
                  <td>{row.trial_id}</td>
                  <td>{format(row.score)}</td>
                  <td>{format(row.efficiency)}</td>
                  <td>{format(row.pressure_rise_pa)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ParallelCoordinatesPlot rows={rows} />
      </div>
    </section>
  );
}

function ParallelCoordinatesPlot({ rows }: { rows: OptimizationResponse["leaderboard"] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const dimensions = useMemo(() => {
    if (rows.length === 0) {
      return [];
    }
    const numericKeys = Object.keys(rows[0]).filter((key) =>
      rows.some((row) => typeof row[key] === "number")
    );
    return numericKeys.slice(0, 10).map((key) => ({
      label: key,
      values: rows.map((row) => (typeof row[key] === "number" ? row[key] : null))
    }));
  }, [rows]);

  useEffect(() => {
    if (!ref.current || dimensions.length === 0) {
      return;
    }
    let cancelled = false;
    void import("plotly.js-dist-min").then((Plotly) => {
      if (cancelled || !ref.current) {
        return;
      }
      Plotly.newPlot(
        ref.current,
        [
          {
            type: "parcoords",
            line: { color: rows.map((row) => Number(row.score ?? 0)), colorscale: "Viridis" },
            dimensions
          }
        ],
        {
          margin: { l: 44, r: 24, t: 20, b: 24 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: "Inter, system-ui, sans-serif", size: 11, color: "#334155" }
        },
        { displayModeBar: false, responsive: true }
      );
    });
    return () => {
      cancelled = true;
    };
  }, [dimensions, rows]);

  if (rows.length === 0) {
    return <div className="plotly-panel empty-state">No optimization leaderboard found.</div>;
  }
  return <div ref={ref} className="plotly-panel" />;
}

function format(value: unknown) {
  return typeof value === "number" ? value.toPrecision(4) : "-";
}
