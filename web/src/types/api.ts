import type { FanCFDConfig } from "./config";

export type JobStatus = "pending" | "running" | "success" | "failed" | "cancelled";
export type JobType = "geometry" | "run" | "postprocess" | "optimize";

export interface ValidationErrorItem {
  loc: Array<string | number>;
  path: string;
  msg: string;
  type?: string | null;
}

export interface ValidationResponse {
  valid: boolean;
  errors: ValidationErrorItem[];
  data?: FanCFDConfig | null;
}

export interface ConfigListItem {
  id: string;
  name: string;
  path: string;
  size_bytes: number;
  updated_at: string;
  fan_name?: string | null;
  stages?: number | null;
  valid: boolean;
}

export interface ConfigDetail extends ConfigListItem {
  yaml_text: string;
  data?: FanCFDConfig | null;
  validation_errors: ValidationErrorItem[];
}

export interface ProgressInfo {
  step?: string | null;
  step_index?: number | null;
  total_steps?: number | null;
  iteration?: number | null;
  total_iterations?: number | null;
  residuals: Record<string, number>;
  trial_id?: number | null;
  n_complete?: number | null;
  n_total?: number | null;
}

export interface JobRecord {
  id: string;
  type: JobType;
  config_id: string;
  options: Record<string, unknown>;
  command: string[];
  run_id: string;
  run_dir: string;
  status: JobStatus;
  progress: ProgressInfo;
  created_at: string;
  started_at?: string | null;
  ended_at?: string | null;
  exit_code?: number | null;
  log_path?: string | null;
  error?: string | null;
}

export interface JobLogResponse {
  job_id: string;
  lines: string[];
}

export interface StlFileItem {
  name: string;
  path: string;
  url: string;
  size_bytes: number;
}

export interface ResultsResponse {
  run_id: string;
  metrics: Record<string, number | null>;
  mesh: Record<string, number | boolean | null>;
  convergence: Record<string, unknown>;
  per_stage_torque: Record<string, number | null>;
}

export interface ConvergencePoint {
  iteration: number;
  residuals: Record<string, number>;
}

export interface OptimizationResponse {
  run_id: string;
  leaderboard: Array<Record<string, string | number | boolean | null>>;
}

export type JobWsMessage =
  | { type: "log"; line: string; timestamp: string }
  | {
      type: "progress";
      step?: string;
      step_index?: number;
      total_steps?: number;
      timestamp: string;
    }
  | {
      type: "iteration";
      iteration: number;
      total_iterations?: number | null;
      residuals: Record<string, number>;
      timestamp: string;
    }
  | {
      type: "trial_complete";
      trial_id: number;
      score: number;
      n_complete: number;
      n_total: number;
      timestamp: string;
    }
  | {
      type: "status";
      status: JobStatus;
      exit_code?: number | null;
      timestamp: string;
    };

