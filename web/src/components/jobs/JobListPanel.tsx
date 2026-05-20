import { Ban, Circle, RotateCcw } from "lucide-react";
import type { JobRecord, JobStatus } from "../../types/api";

interface JobListPanelProps {
  jobs: JobRecord[];
  activeJobId?: string | null;
  onSelect: (jobId: string) => void;
  onCancel: (jobId: string) => void;
  refetching?: boolean;
}

export default function JobListPanel({
  jobs,
  activeJobId,
  onSelect,
  onCancel,
  refetching
}: JobListPanelProps) {
  return (
    <aside className="list-panel jobs-panel">
      <div className="panel-header">
        <div>
          <h2>Jobs</h2>
          <p>{jobs.length} tracked run(s)</p>
        </div>
        <RotateCcw size={17} className={refetching ? "spin" : ""} />
      </div>
      <div className="job-list">
        {jobs.map((job) => (
          <button
            key={job.id}
            type="button"
            className={`job-card ${job.id === activeJobId ? "selected" : ""}`}
            onClick={() => onSelect(job.id)}
          >
            <div className="job-card-main">
              <StatusBadge status={job.status} />
              <strong>{job.type}</strong>
              <span>{job.config_id}</span>
            </div>
            <div className="job-card-meta">
              <span>{job.progress.step ?? job.run_id}</span>
              {(job.status === "running" || job.status === "pending") && (
                <span
                  role="button"
                  tabIndex={0}
                  className="job-cancel"
                  onClick={(event) => {
                    event.stopPropagation();
                    onCancel(job.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      event.stopPropagation();
                      onCancel(job.id);
                    }
                  }}
                >
                  <Ban size={14} />
                </span>
              )}
            </div>
          </button>
        ))}
        {jobs.length === 0 && <div className="empty-state">No jobs launched yet.</div>}
      </div>
    </aside>
  );
}

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`status-badge ${status}`}>
      <Circle size={8} fill="currentColor" />
      {status}
    </span>
  );
}

