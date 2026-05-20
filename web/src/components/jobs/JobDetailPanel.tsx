import { Ban, ExternalLink, TerminalSquare } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ResidualPoint, TrialPoint } from "../../hooks/useJobWebSocket";
import { StatusBadge } from "./JobListPanel";
import type { JobRecord, JobStatus } from "../../types/api";

interface JobDetailPanelProps {
  job?: JobRecord;
  logs: string[];
  residuals: ResidualPoint[];
  trials: TrialPoint[];
  liveStatus?: JobStatus | null;
  connected: boolean;
  onCancel: (jobId: string) => void;
}

export default function JobDetailPanel({
  job,
  logs,
  residuals,
  trials,
  liveStatus,
  connected,
  onCancel
}: JobDetailPanelProps) {
  if (!job) {
    return <section className="detail-panel empty-detail">Select a job to inspect logs and progress.</section>;
  }

  const fields = Array.from(
    new Set(residuals.flatMap((point) => Object.keys(point).filter((key) => key !== "iteration")))
  );
  const status = liveStatus ?? job.status;

  return (
    <section className="detail-panel">
      <header className="job-meta-header">
        <div>
          <div className="eyebrow-row">
            <StatusBadge status={status} />
            <span>{connected ? "WebSocket live" : "Polling snapshot"}</span>
          </div>
          <h1>{job.run_id}</h1>
          <p>{job.command.join(" ")}</p>
        </div>
        <div className="header-actions">
          <a className="button" href={`/viewer/${job.run_id}`}>
            <ExternalLink size={16} />
            Viewer
          </a>
          <a className="button" href={`/results/${job.run_id}`}>
            <ExternalLink size={16} />
            Results
          </a>
          {(job.status === "running" || job.status === "pending") && (
            <button className="button danger" type="button" onClick={() => onCancel(job.id)}>
              <Ban size={16} />
              Cancel
            </button>
          )}
        </div>
      </header>

      <PipelineStepIndicator current={job.progress.step_index ?? 0} total={job.progress.total_steps ?? 4} />

      <div className="run-grid">
        <div className="progress-panel">
          <h2>Iterations</h2>
          <IterationProgress
            current={job.progress.iteration ?? residuals.at(-1)?.iteration ?? 0}
            total={job.progress.total_iterations ?? 0}
          />
        </div>
        {job.type === "optimize" && (
          <div className="progress-panel">
            <h2>Optimization</h2>
            <TrialProgress trials={trials} total={job.progress.n_total ?? 0} />
          </div>
        )}
      </div>

      <section className="chart-panel">
        <div className="section-heading row">
          <div>
            <h2>Residuals</h2>
            <span>Rolling live window</span>
          </div>
        </div>
        <div className="chart-frame">
          {residuals.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={residuals}>
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
            <div className="empty-state">Residual data will appear after solver output starts.</div>
          )}
        </div>
      </section>

      {job.type === "optimize" && (
        <section className="table-panel">
          <h2>Live leaderboard</h2>
          <table>
            <thead>
              <tr>
                <th>Trial</th>
                <th>Score</th>
                <th>Complete</th>
              </tr>
            </thead>
            <tbody>
              {trials.map((trial) => (
                <tr key={trial.trial_id}>
                  <td>{trial.trial_id}</td>
                  <td>{trial.score.toFixed(4)}</td>
                  <td>
                    {trial.n_complete} / {trial.n_total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="log-panel">
        <div className="section-heading row">
          <div>
            <h2>Logs</h2>
            <span>{logs.length} streamed line(s)</span>
          </div>
          <TerminalSquare size={18} />
        </div>
        <pre>{logs.slice(-1000).join("\n")}</pre>
      </section>
    </section>
  );
}

function PipelineStepIndicator({ current, total }: { current: number; total: number }) {
  const steps = Array.from({ length: total }, (_, index) => index + 1);
  return (
    <div className="pipeline">
      {steps.map((step) => (
        <div key={step} className={step <= current ? "complete" : ""}>
          <span>{step}</span>
        </div>
      ))}
    </div>
  );
}

function IterationProgress({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (current / total) * 100) : 0;
  return (
    <div className="progress-meter">
      <div>
        <strong>{current}</strong>
        <span>/ {total || "?"} iterations</span>
      </div>
      <div className="bar">
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function TrialProgress({ trials, total }: { trials: TrialPoint[]; total: number }) {
  const complete = trials.at(-1)?.n_complete ?? 0;
  const pct = total > 0 ? Math.min(100, (complete / total) * 100) : 0;
  return (
    <div className="progress-meter">
      <div>
        <strong>{complete}</strong>
        <span>/ {total || "?"} trials</span>
      </div>
      <div className="bar amber">
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const chartColors = ["#0f8f8a", "#d97706", "#4253b5", "#c2410c", "#7c3aed", "#059669"];

