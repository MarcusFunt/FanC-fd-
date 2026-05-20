from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    GEOMETRY = "geometry"
    RUN = "run"
    POSTPROCESS = "postprocess"
    OPTIMIZE = "optimize"


@dataclass
class ProgressInfo:
    step: str | None = None
    step_index: int | None = None
    total_steps: int | None = None
    iteration: int | None = None
    total_iterations: int | None = None
    residuals: dict[str, float] = field(default_factory=dict)
    trial_id: int | None = None
    n_complete: int | None = None
    n_total: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "iteration": self.iteration,
            "total_iterations": self.total_iterations,
            "residuals": self.residuals,
            "trial_id": self.trial_id,
            "n_complete": self.n_complete,
            "n_total": self.n_total,
        }


@dataclass
class JobRecord:
    id: str
    type: JobType
    config_id: str
    options: dict[str, Any]
    command: list[str]
    run_id: str
    run_dir: Path
    status: JobStatus = JobStatus.PENDING
    progress: ProgressInfo = field(default_factory=ProgressInfo)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    ended_at: datetime | None = None
    exit_code: int | None = None
    log_path: Path | None = None
    error: str | None = None
    log_lines: deque[str] = field(default_factory=lambda: deque(maxlen=50_000))
    process: Any | None = field(default=None, repr=False, compare=False)

    def append_log(self, line: str) -> None:
        self.log_lines.append(line)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "config_id": self.config_id,
            "options": self.options,
            "command": self.command,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "exit_code": self.exit_code,
            "log_path": str(self.log_path) if self.log_path else None,
            "error": self.error,
        }

