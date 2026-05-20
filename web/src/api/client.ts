import axios from "axios";
import type {
  ConfigDetail,
  ConfigListItem,
  ConvergencePoint,
  JobLogResponse,
  JobRecord,
  JobType,
  OptimizationResponse,
  ResultsResponse,
  StlFileItem,
  ValidationResponse
} from "../types/api";
import type { FanCFDConfig } from "../types/config";

export const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 30_000
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail ?? error.message;
    return Promise.reject(new Error(Array.isArray(message) ? message.join(", ") : message));
  }
);

export const configsApi = {
  list: async () => (await apiClient.get<ConfigListItem[]>("/configs/")).data,
  get: async (id: string) => (await apiClient.get<ConfigDetail>(`/configs/${id}`)).data,
  validate: async (payload: { yaml_text?: string; data?: FanCFDConfig }) =>
    (await apiClient.post<ValidationResponse>("/configs/validate", payload)).data,
  save: async (payload: { id?: string; yaml_text?: string; data?: FanCFDConfig }) =>
    (await apiClient.post<ConfigDetail>("/configs/", payload)).data,
  update: async (id: string, payload: { yaml_text?: string; data?: FanCFDConfig }) =>
    (await apiClient.put<ConfigDetail>(`/configs/${id}`, payload)).data,
  remove: async (id: string) => {
    await apiClient.delete(`/configs/${id}`);
  },
  schema: async () => (await apiClient.get<Record<string, unknown>>("/configs/schema")).data
};

export const jobsApi = {
  list: async () => (await apiClient.get<JobRecord[]>("/jobs/")).data,
  get: async (id: string) => (await apiClient.get<JobRecord>(`/jobs/${id}`)).data,
  create: async (payload: { type: JobType; config_id: string; options?: Record<string, unknown> }) =>
    (await apiClient.post<JobRecord>("/jobs/", payload)).data,
  cancel: async (id: string) => (await apiClient.delete<JobRecord>(`/jobs/${id}`)).data,
  logs: async (id: string) => (await apiClient.get<JobLogResponse>(`/jobs/${id}/logs`)).data
};

export const resultsApi = {
  get: async (runId: string) => (await apiClient.get<ResultsResponse>(`/results/${runId}`)).data,
  convergence: async (runId: string) =>
    (await apiClient.get<ConvergencePoint[]>(`/results/${runId}/convergence`)).data,
  stlFiles: async (runId: string) =>
    (await apiClient.get<StlFileItem[]>(`/results/${runId}/stl-files`)).data,
  optimization: async (runId: string) =>
    (await apiClient.get<OptimizationResponse>(`/results/${runId}/optimization`)).data
};

