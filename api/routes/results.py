from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.models.api_types import (
    ConvergencePoint,
    OptimizationResponse,
    ResultsResponse,
    StlFileItem,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "runs"

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.get("/{run_id}", response_model=ResultsResponse)
def get_results(run_id: str) -> dict:
    run_dir = _safe_run_dir(run_id)
    result_path = _find_results_json(run_dir)
    if result_path is None:
        raise HTTPException(status_code=404, detail="results.json not found for run.")

    data = json.loads(result_path.read_text(encoding="utf-8"))
    return {
        "run_id": run_id,
        "metrics": {
            "flow_rate_m3_s": data.get("flow_rate_m3_s"),
            "pressure_rise_pa": data.get("pressure_rise_pa"),
            "torque_nm": data.get("torque_nm"),
            "shaft_power_w": data.get("shaft_power_w"),
            "efficiency": data.get("efficiency"),
        },
        "mesh": data.get("mesh") or {},
        "convergence": data.get("convergence") or {},
        "per_stage_torque": data.get("per_stage_torque") or {},
    }


@router.get("/{run_id}/convergence", response_model=list[ConvergencePoint])
def get_convergence(run_id: str) -> list[dict]:
    run_dir = _safe_run_dir(run_id)
    log_path = _find_solver_log(run_dir)
    if log_path is None:
        return []
    return _parse_convergence(log_path.read_text(encoding="utf-8", errors="replace"))


@router.get("/{run_id}/stl-files", response_model=list[StlFileItem])
def get_stl_files(run_id: str) -> list[dict]:
    run_dir = _safe_run_dir(run_id)
    geometry_dir = run_dir / "geometry"
    if not geometry_dir.exists():
        return []

    files: list[dict[str, Any]] = []
    for path in sorted(geometry_dir.glob("*.stl")):
        rel = path.relative_to(RUNS_DIR).as_posix()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "url": f"/files/runs/{rel}",
                "size_bytes": path.stat().st_size,
            }
        )
    return files


@router.get("/{run_id}/optimization", response_model=OptimizationResponse)
def get_optimization(run_id: str) -> dict:
    run_dir = _safe_run_dir(run_id)
    leaderboard_path = _find_leaderboard(run_dir)
    if leaderboard_path is None:
        return {"run_id": run_id, "leaderboard": []}

    rows: list[dict[str, Any]] = []
    with open(leaderboard_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({key: _coerce_csv_value(value) for key, value in row.items()})
    return {"run_id": run_id, "leaderboard": rows}


def _safe_run_dir(run_id: str) -> Path:
    if not run_id or run_id in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid run id.")

    candidate = (RUNS_DIR / run_id).resolve()
    runs_root = RUNS_DIR.resolve()
    if candidate.parent != runs_root:
        raise HTTPException(status_code=400, detail="Invalid run id.")
    if not candidate.exists() or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="Run not found.")
    return candidate


def _find_results_json(run_dir: Path) -> Path | None:
    candidates = [
        run_dir / "results" / "results.json",
        run_dir / "results.json",
        run_dir / "openfoam" / "results.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(run_dir.rglob("results.json"))
    return matches[0] if matches else None


def _find_solver_log(run_dir: Path) -> Path | None:
    candidates = [
        run_dir / "openfoam" / "log.simpleFoam",
        run_dir / "openfoam" / "log.pimpleFoam",
        run_dir / "openfoam" / "log.rhoSimpleFoam",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(run_dir.rglob("log.simpleFoam"))
    return matches[0] if matches else None


def _find_leaderboard(run_dir: Path) -> Path | None:
    candidates = [
        run_dir / "optimization" / "leaderboard.csv",
        run_dir / "leaderboard.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(run_dir.rglob("leaderboard.csv"))
    return matches[0] if matches else None


def _parse_convergence(log_text: str) -> list[dict]:
    points: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in log_text.splitlines():
        time_match = re.search(r"^Time = ([\d.]+)s?", line)
        if time_match:
            if current is not None:
                points.append(current)
            current = {
                "iteration": int(float(time_match.group(1))),
                "residuals": {},
            }
            continue

        residual_match = re.search(
            r"Solving for\s+(\w+),.*?Final residual\s*=\s*([\d.eE+\-]+)",
            line,
        )
        if residual_match and current is not None:
            current["residuals"][residual_match.group(1)] = float(residual_match.group(2))

    if current is not None:
        points.append(current)
    return points


def _coerce_csv_value(value: str | None) -> Any:
    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"nan", ""}:
        return None
    try:
        if "." in value or "e" in lowered:
            return float(value)
        return int(value)
    except ValueError:
        return value
