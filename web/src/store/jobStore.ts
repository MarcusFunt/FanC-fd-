import { create } from "zustand";
import type { JobRecord } from "../types/api";

interface JobStore {
  jobs: JobRecord[];
  activeJobId: string | null;
  setJobs: (jobs: JobRecord[]) => void;
  upsertJob: (job: JobRecord) => void;
  setActiveJobId: (jobId: string | null) => void;
}

export const useJobStore = create<JobStore>((set) => ({
  jobs: [],
  activeJobId: null,
  setJobs: (jobs) => set({ jobs }),
  upsertJob: (job) =>
    set((state) => {
      const exists = state.jobs.some((candidate) => candidate.id === job.id);
      return {
        jobs: exists
          ? state.jobs.map((candidate) => (candidate.id === job.id ? job : candidate))
          : [job, ...state.jobs]
      };
    }),
  setActiveJobId: (activeJobId) => set({ activeJobId })
}));

