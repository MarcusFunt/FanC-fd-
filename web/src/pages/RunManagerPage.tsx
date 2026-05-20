import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { jobsApi } from "../api/client";
import JobDetailPanel from "../components/jobs/JobDetailPanel";
import JobListPanel from "../components/jobs/JobListPanel";
import { useJobWebSocket } from "../hooks/useJobWebSocket";
import { useJobStore } from "../store/jobStore";

export default function RunManagerPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setJobs = useJobStore((state) => state.setJobs);
  const setActiveJobId = useJobStore((state) => state.setActiveJobId);

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: jobsApi.list,
    refetchInterval: 5000
  });

  useEffect(() => {
    if (jobsQuery.data) {
      setJobs(jobsQuery.data);
      if (!jobId && jobsQuery.data[0]) {
        navigate(`/runs/${jobsQuery.data[0].id}`, { replace: true });
      }
    }
  }, [jobId, jobsQuery.data, navigate, setJobs]);

  useEffect(() => {
    setActiveJobId(jobId ?? null);
  }, [jobId, setActiveJobId]);

  const activeJob = useMemo(
    () => jobsQuery.data?.find((job) => job.id === jobId),
    [jobId, jobsQuery.data]
  );
  const live = useJobWebSocket(jobId);

  const cancelMutation = useMutation({
    mutationFn: jobsApi.cancel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });

  return (
    <div className="workspace runs-workspace">
      <JobListPanel
        jobs={jobsQuery.data ?? []}
        activeJobId={jobId}
        onSelect={(id) => navigate(`/runs/${id}`)}
        onCancel={(id) => cancelMutation.mutate(id)}
        refetching={jobsQuery.isFetching}
      />
      <JobDetailPanel
        job={activeJob}
        logs={live.logs}
        residuals={live.residuals}
        trials={live.trials}
        liveStatus={live.status}
        connected={live.connected}
        onCancel={(id) => cancelMutation.mutate(id)}
      />
    </div>
  );
}
