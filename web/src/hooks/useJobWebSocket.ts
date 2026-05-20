import { useEffect, useMemo, useState } from "react";
import type { JobStatus, JobWsMessage } from "../types/api";

export interface ResidualPoint {
  iteration: number;
  [field: string]: number;
}

export interface TrialPoint {
  trial_id: number;
  score: number;
  n_complete: number;
  n_total: number;
}

export function useJobWebSocket(jobId?: string | null) {
  const [logs, setLogs] = useState<string[]>([]);
  const [residuals, setResiduals] = useState<ResidualPoint[]>([]);
  const [trials, setTrials] = useState<TrialPoint[]>([]);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    setLogs([]);
    setResiduals([]);
    setTrials([]);
    setStatus(null);

    if (!jobId) {
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/jobs/${jobId}/logs`);

    socket.addEventListener("open", () => setConnected(true));
    socket.addEventListener("close", () => setConnected(false));
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data) as JobWsMessage;
      if (message.type === "log") {
        setLogs((current) => [...current.slice(-4999), message.line]);
      }
      if (message.type === "iteration") {
        setResiduals((current) => [
          ...current.slice(-199),
          { iteration: message.iteration, ...message.residuals }
        ]);
      }
      if (message.type === "trial_complete") {
        setTrials((current) => [...current, message]);
      }
      if (message.type === "status") {
        setStatus(message.status);
      }
    });

    return () => {
      socket.close();
    };
  }, [jobId]);

  return useMemo(
    () => ({ logs, residuals, trials, status, connected }),
    [connected, logs, residuals, status, trials]
  );
}

