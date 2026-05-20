import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ConvergencePoint } from "../../types/api";

interface ConvergencePlotProps {
  data: ConvergencePoint[];
}

export default function ConvergencePlot({ data }: ConvergencePlotProps) {
  const chartData = data.map((point) => ({
    iteration: point.iteration,
    ...point.residuals
  }));
  const fields = Array.from(new Set(data.flatMap((point) => Object.keys(point.residuals))));

  return (
    <section className="chart-panel">
      <div className="section-heading row">
        <div>
          <h2>Convergence</h2>
          <span>{data.length} solver timestep(s)</span>
        </div>
      </div>
      <div className="chart-frame tall">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="iteration" />
              <YAxis scale="log" domain={["auto", "auto"]} allowDataOverflow />
              <Tooltip />
              {fields.map((field, index) => (
                <Line
                  key={field}
                  type="monotone"
                  dot={false}
                  stroke={chartColors[index % chartColors.length]}
                  dataKey={field}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">No convergence log was found for this run.</div>
        )}
      </div>
    </section>
  );
}

const chartColors = ["#0f8f8a", "#d97706", "#4253b5", "#c2410c", "#7c3aed", "#059669"];

