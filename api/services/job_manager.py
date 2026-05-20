from __future__ import annotations

import asyncio
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fan_cfd.config import load_config

from api.models.job import JobRecord, JobStatus, JobType
from api.services.config_validator import config_path_for_id
from api.ws.log_streamer import log_streamer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    def list_jobs(self) -> list[JobRecord]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def launch_job(
        self,
        job_type: JobType,
        config_id: str,
        options: dict[str, Any] | None = None,
    ) -> JobRecord:
        options = options or {}
        config_path = config_path_for_id(config_id)
        config = load_config(config_path)

        job_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fan_name = _slugify(config.fan.name)
        run_id = f"{fan_name}_{job_type.value}_{timestamp}_{job_id}"
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_path, run_dir / "config.yaml")

        command = self._build_command(job_type, config_path, run_dir, options)
        record = JobRecord(
            id=job_id,
            type=job_type,
            config_id=config_id,
            options=options,
            command=command,
            run_id=run_id,
            run_dir=run_dir,
        )
        record.progress.total_iterations = config.cfd.run.n_iterations
        if job_type == JobType.OPTIMIZE:
            record.progress.n_total = int(options.get("n_trials", 20))

        async with self._lock:
            self._jobs[job_id] = record
            self._tasks[job_id] = asyncio.create_task(self._run_job(record))

        return record

    async def cancel_job(self, job_id: str) -> None:
        record = self._jobs.get(job_id)
        if record is None:
            return
        if record.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
            return

        record.status = JobStatus.CANCELLED
        record.append_log("Cancellation requested.")
        await log_streamer.publish(
            job_id,
            {
                "type": "log",
                "line": "Cancellation requested.",
            },
        )
        if record.process is not None and record.process.returncode is None:
            record.process.terminate()
        await log_streamer.publish(
            job_id,
            {
                "type": "status",
                "status": JobStatus.CANCELLED.value,
                "exit_code": record.exit_code,
            },
        )

    def get_logs(self, record: JobRecord) -> list[str]:
        if record.log_path and record.log_path.exists():
            return record.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return list(record.log_lines)

    def _build_command(
        self,
        job_type: JobType,
        config_path: Path,
        run_dir: Path,
        options: dict[str, Any],
    ) -> list[str]:
        scripts_dir = PROJECT_ROOT / "scripts"
        if job_type == JobType.GEOMETRY:
            command = _python_script_command(
                scripts_dir / "generate_geometry.py",
                "--config",
                str(config_path),
                "--output-dir",
                str(run_dir / "geometry"),
            )
            if options.get("validate_only"):
                command.append("--validate-only")
            return command

        if job_type == JobType.RUN:
            command = _python_script_command(
                scripts_dir / "run_case.py",
                "--config",
                str(config_path),
                "--output-dir",
                str(run_dir),
            )
            for flag in ("skip_geometry", "skip_mesh", "skip_solve", "skip_render"):
                if options.get(flag):
                    command.append(f"--{flag.replace('_', '-')}")
            return command

        if job_type == JobType.POSTPROCESS:
            case_dir = options.get("case_dir")
            if not case_dir and options.get("run_id"):
                case_dir = str(RUNS_DIR / str(options["run_id"]) / "openfoam")
            if not case_dir:
                raise ValueError("postprocess jobs require options.case_dir or options.run_id.")
            output_path = run_dir / "results" / "results.json"
            return _python_script_command(
                scripts_dir / "postprocess_case.py",
                "--case",
                str(case_dir),
                "--config",
                str(config_path),
                "--output",
                str(output_path),
            )

        if job_type == JobType.OPTIMIZE:
            return _python_script_command(
                scripts_dir / "optimize.py",
                "--config",
                str(config_path),
                "--n-trials",
                str(int(options.get("n_trials", 20))),
                "--method",
                str(options.get("method", "random")),
                "--output-dir",
                str(run_dir / "optimization"),
            )

        raise ValueError(f"Unsupported job type: {job_type}")

    async def _run_job(self, record: JobRecord) -> None:
        record.status = JobStatus.RUNNING
        record.started_at = datetime.now(timezone.utc)
        await self._handle_line(record, f"Launching job {record.id}: {' '.join(record.command)}")
        await log_streamer.publish(
            record.id,
            {
                "type": "status",
                "status": record.status.value,
                "exit_code": None,
            },
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *record.command,
                cwd=str(PROJECT_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            record.process = proc

            assert proc.stdout is not None
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                line = raw.decode(errors="replace").rstrip("\r\n")
                await self._handle_line(record, line)

            record.exit_code = await proc.wait()
            if record.status == JobStatus.CANCELLED:
                final_status = JobStatus.CANCELLED
            elif record.exit_code == 0:
                final_status = JobStatus.SUCCESS
            else:
                final_status = JobStatus.FAILED
            record.status = final_status
        except Exception as exc:
            record.status = JobStatus.FAILED
            record.error = str(exc)
            await self._handle_line(record, f"API job runner failed: {exc}")
        finally:
            record.ended_at = datetime.now(timezone.utc)
            record.append_log(
                f"Job {record.id} finished with status={record.status.value} exit_code={record.exit_code}."
            )
            record.log_path = record.run_dir / f"job_{record.id}.log"
            record.log_path.write_text("\n".join(record.log_lines), encoding="utf-8")
            await log_streamer.publish(
                record.id,
                {
                    "type": "log",
                    "line": (
                        f"Job {record.id} finished with status={record.status.value} "
                        f"exit_code={record.exit_code}."
                    ),
                },
            )
            await log_streamer.publish(
                record.id,
                {
                    "type": "status",
                    "status": record.status.value,
                    "exit_code": record.exit_code,
                },
            )

    async def _handle_line(self, record: JobRecord, line: str) -> None:
        record.append_log(line)
        await log_streamer.publish(
            record.id,
            {
                "type": "log",
                "line": line,
            },
        )

        step_match = re.search(r"===\s*Step\s+(\d+)/(\d+):\s*(.*?)\s*===", line)
        if step_match:
            record.progress.step_index = int(step_match.group(1))
            record.progress.total_steps = int(step_match.group(2))
            record.progress.step = step_match.group(3)
            await log_streamer.publish(
                record.id,
                {
                    "type": "progress",
                    "step": record.progress.step,
                    "step_index": record.progress.step_index,
                    "total_steps": record.progress.total_steps,
                },
            )

        time_match = re.search(r"\bTime\s*=\s*([\d.]+)", line)
        if time_match:
            record.progress.iteration = int(float(time_match.group(1)))
            await self._publish_iteration(record)

        residual_match = re.search(
            r"Solving for\s+(\w+),.*?Final residual\s*=\s*([\d.eE+\-]+)",
            line,
        )
        if residual_match:
            record.progress.residuals[residual_match.group(1)] = float(
                residual_match.group(2)
            )
            await self._publish_iteration(record)

        trial_match = re.search(r"---\s*Trial\s+(\d+)/(\d+)\s*---", line)
        if trial_match:
            record.progress.trial_id = int(trial_match.group(1))
            record.progress.n_total = int(trial_match.group(2))
            await log_streamer.publish(
                record.id,
                {
                    "type": "progress",
                    "step": f"Optimization trial {record.progress.trial_id}",
                    "step_index": record.progress.trial_id,
                    "total_steps": record.progress.n_total,
                },
            )

        score_match = re.search(r"Trial\s+(\d+):\s+score=([\d.eE+\-]+)", line)
        if score_match:
            score = float(score_match.group(2))
            trial_id = int(score_match.group(1))
            total = record.progress.n_total or int(record.options.get("n_trials", 20))
            n_complete = min(total, max(record.progress.trial_id or 0, trial_id + 1))
            record.progress.n_complete = n_complete
            await log_streamer.publish(
                record.id,
                {
                    "type": "trial_complete",
                    "trial_id": trial_id,
                    "score": score,
                    "n_complete": n_complete,
                    "n_total": total,
                },
            )

    async def _publish_iteration(self, record: JobRecord) -> None:
        if record.progress.iteration is None:
            return
        await log_streamer.publish(
            record.id,
            {
                "type": "iteration",
                "iteration": record.progress.iteration,
                "total_iterations": record.progress.total_iterations,
                "residuals": record.progress.residuals,
            },
        )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower() or "fan"


def _python_script_command(script_path: Path, *args: str) -> list[str]:
    return [sys.executable, "-u", str(script_path), *args]


job_manager = JobManager()
