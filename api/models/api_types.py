from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.models.job import JobStatus, JobType


class ValidationErrorItem(BaseModel):
    loc: list[str | int] = Field(default_factory=list)
    path: str
    msg: str
    type: str | None = None


class ValidationRequest(BaseModel):
    yaml_text: str | None = None
    data: dict[str, Any] | None = None


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    data: dict[str, Any] | None = None


class ConfigSaveRequest(BaseModel):
    id: str | None = None
    yaml_text: str | None = None
    data: dict[str, Any] | None = None


class ConfigListItem(BaseModel):
    id: str
    name: str
    path: str
    size_bytes: int
    updated_at: str
    fan_name: str | None = None
    stages: int | None = None
    valid: bool


class ConfigDetail(ConfigListItem):
    yaml_text: str
    data: dict[str, Any] | None = None
    validation_errors: list[ValidationErrorItem] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    step: str | None = None
    step_index: int | None = None
    total_steps: int | None = None
    iteration: int | None = None
    total_iterations: int | None = None
    residuals: dict[str, float] = Field(default_factory=dict)
    trial_id: int | None = None
    n_complete: int | None = None
    n_total: int | None = None


class JobCreateRequest(BaseModel):
    type: JobType
    config_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    type: JobType
    config_id: str
    options: dict[str, Any] = Field(default_factory=dict)
    command: list[str]
    run_id: str
    run_dir: str
    status: JobStatus
    progress: ProgressResponse
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    log_path: str | None = None
    error: str | None = None


class JobLogResponse(BaseModel):
    job_id: str
    lines: list[str]


class StlFileItem(BaseModel):
    name: str
    path: str
    url: str
    size_bytes: int


class ResultsResponse(BaseModel):
    run_id: str
    metrics: dict[str, Any]
    mesh: dict[str, Any] = Field(default_factory=dict)
    convergence: dict[str, Any] = Field(default_factory=dict)
    per_stage_torque: dict[str, float | None] = Field(default_factory=dict)


class ConvergencePoint(BaseModel):
    iteration: int
    residuals: dict[str, float] = Field(default_factory=dict)


class OptimizationResponse(BaseModel):
    run_id: str
    leaderboard: list[dict[str, Any]] = Field(default_factory=list)

