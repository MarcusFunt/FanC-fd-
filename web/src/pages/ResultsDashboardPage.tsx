import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { jobsApi, resultsApi } from "../api/client";
import ConvergencePlot from "../components/results/ConvergencePlot";
import MeshQualityPanel from "../components/results/MeshQualityPanel";
import MetricCardsRow from "../components/results/MetricCardsRow";
import OptimizationSection from "../components/results/OptimizationSection";

interface ResultsDashboardPageProps {
  optimizeMode?: boolean;
}

export default function ResultsDashboardPage({ optimizeMode }: ResultsDashboardPageProps) {
  const params = useParams();
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: jobsApi.list,
    enabled: params.runId === "latest" || Boolean(params.jobId)
  });

  const runId = useMemo(() => {
    if (params.runId && params.runId !== "latest") {
      return params.runId;
    }
    if (params.jobId) {
      return jobsQuery.data?.find((job) => job.id === params.jobId)?.run_id;
    }
    return jobsQuery.data?.[0]?.run_id;
  }, [jobsQuery.data, params.jobId, params.runId]);

  const resultsQuery = useQuery({
    queryKey: ["results", runId],
    queryFn: () => resultsApi.get(runId!),
    enabled: Boolean(runId)
  });
  const convergenceQuery = useQuery({
    queryKey: ["results", runId, "convergence"],
    queryFn: () => resultsApi.convergence(runId!),
    enabled: Boolean(runId)
  });
  const optimizationQuery = useQuery({
    queryKey: ["results", runId, "optimization"],
    queryFn: () => resultsApi.optimization(runId!),
    enabled: Boolean(runId)
  });

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <div>
          <h1>{runId ?? "Results"}</h1>
          <p>{optimizeMode ? "Optimization job summary" : "Performance, convergence, and mesh quality"}</p>
        </div>
      </header>

      {!runId && <div className="empty-state wide">Launch or select a job to inspect results.</div>}
      {runId && resultsQuery.isError && (
        <div className="inline-error">
          {resultsQuery.error instanceof Error ? resultsQuery.error.message : "Could not load results."}
        </div>
      )}

      <MetricCardsRow results={resultsQuery.data} />

      <div className="dashboard-grid">
        <ConvergencePlot data={convergenceQuery.data ?? []} />
        <MeshQualityPanel results={resultsQuery.data} />
      </div>

      <section className="table-panel">
        <div className="section-heading row">
          <div>
            <h2>Per-stage torque</h2>
            <span>Rotor contribution</span>
          </div>
        </div>
        <div className="torque-bars">
          {Object.entries(resultsQuery.data?.per_stage_torque ?? {}).map(([stage, torque]) => (
            <div key={stage} className="torque-row">
              <span>{stage}</span>
              <div>
                <em style={{ width: `${Math.min(100, Math.abs((torque ?? 0) * 1000))}%` }} />
              </div>
              <strong>{typeof torque === "number" ? torque.toFixed(5) : "-"} N*m</strong>
            </div>
          ))}
        </div>
      </section>

      <OptimizationSection optimization={optimizationQuery.data} />
    </div>
  );
}
