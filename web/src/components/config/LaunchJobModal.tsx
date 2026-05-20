import { useState } from "react";
import { Play, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { jobsApi } from "../../api/client";
import type { JobType } from "../../types/api";

interface LaunchJobModalProps {
  configId: string | null;
  open: boolean;
  onClose: () => void;
}

export default function LaunchJobModal({ configId, open, onClose }: LaunchJobModalProps) {
  const navigate = useNavigate();
  const [type, setType] = useState<JobType>("geometry");
  const [nTrials, setNTrials] = useState(20);
  const [method, setMethod] = useState("random");
  const [caseDir, setCaseDir] = useState("");
  const [skipGeometry, setSkipGeometry] = useState(false);
  const [skipMesh, setSkipMesh] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return null;
  }

  const launch = async () => {
    if (!configId) {
      setError("Save the config before launching a job.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const options: Record<string, unknown> = {};
      if (type === "optimize") {
        options.n_trials = nTrials;
        options.method = method;
      }
      if (type === "run") {
        options.skip_geometry = skipGeometry;
        options.skip_mesh = skipMesh;
      }
      if (type === "postprocess") {
        options.case_dir = caseDir;
      }
      const job = await jobsApi.create({ type, config_id: configId, options });
      onClose();
      navigate(`/runs/${job.id}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not launch job.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="launch-title">
        <div className="modal-header">
          <div>
            <h2 id="launch-title">Launch job</h2>
            <p>{configId ? `Config: ${configId}` : "No saved config selected"}</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="segmented">
          {(["geometry", "run", "postprocess", "optimize"] as JobType[]).map((candidate) => (
            <button
              key={candidate}
              type="button"
              className={candidate === type ? "selected" : ""}
              onClick={() => setType(candidate)}
            >
              {candidate}
            </button>
          ))}
        </div>

        {type === "run" && (
          <div className="modal-options">
            <label className="check-row">
              <input
                type="checkbox"
                checked={skipGeometry}
                onChange={(event) => setSkipGeometry(event.target.checked)}
              />
              Skip geometry
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={skipMesh}
                onChange={(event) => setSkipMesh(event.target.checked)}
              />
              Skip mesh
            </label>
          </div>
        )}

        {type === "postprocess" && (
          <label className="field">
            <span>OpenFOAM case directory</span>
            <input value={caseDir} onChange={(event) => setCaseDir(event.target.value)} />
          </label>
        )}

        {type === "optimize" && (
          <div className="field-grid two">
            <label className="field">
              <span>Trials</span>
              <input
                type="number"
                min={1}
                value={nTrials}
                onChange={(event) => setNTrials(Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Method</span>
              <select value={method} onChange={(event) => setMethod(event.target.value)}>
                <option value="random">Random</option>
                <option value="differential_evolution">Differential evolution</option>
                <option value="bayesian">Bayesian</option>
                <option value="genetic">Genetic</option>
              </select>
            </label>
          </div>
        )}

        {error && <div className="inline-error">{error}</div>}

        <div className="modal-actions">
          <button className="button ghost" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button primary" type="button" onClick={launch} disabled={submitting}>
            <Play size={16} />
            {submitting ? "Launching" : "Launch"}
          </button>
        </div>
      </section>
    </div>
  );
}

