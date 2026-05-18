"""
fan_cfd.openfoam.postprocess
=============================
Extracts fan performance metrics from OpenFOAM postProcessing/ output.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MeshQuality:
    max_non_ortho: float = float("nan")
    max_skewness: float = float("nan")
    n_cells: int = 0
    ok: bool = False


@dataclass
class ConvergenceResult:
    converged: bool = False
    n_iterations: int = 0
    residual_history: dict[str, list[float]] = field(default_factory=dict)
    final_residuals: dict[str, float] = field(default_factory=dict)


@dataclass
class FanPerformance:
    """All extracted fan performance metrics."""

    # Flow
    flow_rate_m3_s: float = float("nan")
    pressure_rise_pa: float = float("nan")

    # Power
    torque_nm: float = float("nan")           # total torque (all rotors)
    per_stage_torque: dict[str, float] = field(default_factory=dict)
    shaft_power_w: float = float("nan")

    # Efficiency
    efficiency: float = float("nan")          # hydraulic efficiency 0–1

    # Quality
    mesh: MeshQuality = field(default_factory=MeshQuality)
    convergence: ConvergenceResult = field(default_factory=ConvergenceResult)

    # Meta
    case_dir: str = ""
    config_name: str = ""


# ---------------------------------------------------------------------------
# PostProcessor
# ---------------------------------------------------------------------------


class PostProcessor:
    """
    Extracts performance data from a completed OpenFOAM case directory.

    Parameters
    ----------
    case_dir : Path
        OpenFOAM case directory containing ``postProcessing/`` and ``log.*``.
    fan : FanConfig
    """

    def __init__(self, case_dir: Path, fan: "FanConfig") -> None:
        self.case_dir = Path(case_dir)
        self.fan = fan
        self._pp_dir = self.case_dir / "postProcessing"

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def extract_all(self) -> FanPerformance:
        """Extract all metrics and return a FanPerformance object."""
        perf = FanPerformance(case_dir=str(self.case_dir), config_name=self.fan.name)

        perf.pressure_rise_pa = self.extract_pressure_rise()
        perf.flow_rate_m3_s = self.extract_flow_rate()
        perf.torque_nm = self.extract_torque()
        perf.per_stage_torque = self.extract_per_stage_torque()
        perf.convergence = self.extract_convergence()
        perf.mesh = self.extract_mesh_quality()

        # Shaft power (total over all rotors)
        total_omega = sum(
            (s.rpm or self.fan.rpm) * 2.0 * math.pi / 60.0
            for s in self.fan.rotor_stages
        )
        if self.fan.rotor_stages:
            avg_omega = total_omega / len(self.fan.rotor_stages)
        else:
            avg_omega = 0.0

        if not math.isnan(perf.torque_nm) and avg_omega > 0:
            perf.shaft_power_w = perf.torque_nm * avg_omega
        else:
            perf.shaft_power_w = float("nan")

        perf.efficiency = self.compute_efficiency(
            perf.pressure_rise_pa,
            perf.flow_rate_m3_s,
            perf.torque_nm,
            (self.fan.rotor_stages[0].rpm or self.fan.rpm) if self.fan.rotor_stages else 0.0,
        )

        return perf

    def extract_pressure_rise(self) -> float:
        """
        Compute pressure rise ΔP = P_outlet - P_inlet from function object output.
        """
        p_out = self._read_surface_field_value("pressureRise")
        p_in = self._read_surface_field_value("pressureInlet")
        if math.isnan(p_out) or math.isnan(p_in):
            return float("nan")
        return p_out - p_in

    def extract_flow_rate(self) -> float:
        """Extract volumetric flow rate from the 'flowRate' function object (m³/s)."""
        val = self._read_surface_field_value("flowRate")
        if not math.isnan(val):
            return abs(val)
        return float("nan")

    def extract_torque(self) -> float:
        """Sum torque (Mz component) over all rotor stages."""
        total = 0.0
        found_any = False
        for stage in self.fan.rotor_stages:
            t = self._read_stage_torque(stage.name)
            if not math.isnan(t):
                total += abs(t)
                found_any = True
        return total if found_any else float("nan")

    def extract_per_stage_torque(self) -> dict[str, float]:
        """Return torque per stage keyed by stage name."""
        result: dict[str, float] = {}
        for stage in self.fan.rotor_stages:
            result[stage.name] = self._read_stage_torque(stage.name)
        return result

    def compute_efficiency(
        self,
        pressure_rise: float,
        flow_rate: float,
        torque: float,
        rpm: float,
    ) -> float:
        """
        Compute hydraulic (total-to-static) efficiency.

        η = ΔP * Q / P_shaft
        P_shaft = torque * ω
        """
        if any(math.isnan(v) for v in [pressure_rise, flow_rate, torque]):
            return float("nan")
        omega = rpm * 2.0 * math.pi / 60.0
        if omega <= 0 or torque <= 0:
            return float("nan")
        shaft_power = torque * omega
        hydraulic_power = pressure_rise * flow_rate
        if shaft_power <= 0:
            return float("nan")
        eff = hydraulic_power / shaft_power
        return float(np.clip(eff, 0.0, 1.0))

    def extract_convergence(self) -> ConvergenceResult:
        """Parse simpleFoam log for residual history."""
        result = ConvergenceResult()
        log_path = self._find_solver_log()
        if log_path is None or not log_path.exists():
            return result

        log_text = log_path.read_text()
        result.n_iterations = _count_time_steps(log_text)
        result.residual_history = _extract_residual_history(log_text)
        if result.residual_history:
            result.final_residuals = {
                k: v[-1] for k, v in result.residual_history.items() if v
            }
            max_res = max(result.final_residuals.values(), default=1.0)
            result.converged = max_res < 1e-3
        return result

    def extract_mesh_quality(self) -> MeshQuality:
        """Parse checkMesh log."""
        mq = MeshQuality()
        log_path = self.case_dir / "log.checkMesh"
        if not log_path.exists():
            return mq

        log_text = log_path.read_text()
        m = re.search(
            r"(?:Max non-orthogonality\s*=\s*|Mesh non-orthogonality\s+Max:\s*)"
            r"([\d.eE+\-]+)",
            log_text,
        )
        if m:
            mq.max_non_ortho = float(m.group(1))
        m = re.search(r"Max skewness\s*=\s*([\d.eE+\-]+)", log_text)
        if m:
            mq.max_skewness = float(m.group(1))
        m = re.search(r"cells:\s+(\d+)", log_text)
        if m:
            mq.n_cells = int(m.group(1))
        mq.ok = "Mesh OK" in log_text or "No errors found" in log_text
        return mq

    def save_results(self, results: FanPerformance, output_path: Path) -> None:
        """Serialize FanPerformance to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "case_dir": results.case_dir,
            "config_name": results.config_name,
            "flow_rate_m3_s": _safe_float(results.flow_rate_m3_s),
            "pressure_rise_pa": _safe_float(results.pressure_rise_pa),
            "torque_nm": _safe_float(results.torque_nm),
            "per_stage_torque": {k: _safe_float(v) for k, v in results.per_stage_torque.items()},
            "shaft_power_w": _safe_float(results.shaft_power_w),
            "efficiency": _safe_float(results.efficiency),
            "mesh": {
                "max_non_ortho": _safe_float(results.mesh.max_non_ortho),
                "max_skewness": _safe_float(results.mesh.max_skewness),
                "n_cells": results.mesh.n_cells,
                "ok": results.mesh.ok,
            },
            "convergence": {
                "converged": results.convergence.converged,
                "n_iterations": results.convergence.n_iterations,
                "final_residuals": {
                    k: _safe_float(v)
                    for k, v in results.convergence.final_residuals.items()
                },
            },
        }
        with open(output_path, "w") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Results saved to %s", output_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_surface_field_value(self, func_name: str) -> float:
        """Read the last value from a surfaceFieldValue function object output."""
        search_dirs = sorted(self._pp_dir.glob(f"{func_name}/*/surface*")) if self._pp_dir.exists() else []
        # Also try time directories
        if not search_dirs and self._pp_dir.exists():
            for time_dir in sorted(self._pp_dir.glob(f"{func_name}/[0-9]*")):
                for csv_file in time_dir.glob("*.dat"):
                    search_dirs.append(csv_file)

        # Fallback: search all dat files
        if not search_dirs and self._pp_dir.exists():
            search_dirs = list(self._pp_dir.rglob(f"*{func_name}*/*.dat"))

        for f in search_dirs:
            try:
                df = pd.read_csv(str(f), comment="#", sep=r"\s+", header=None)
                if len(df.columns) >= 2:
                    return float(df.iloc[-1, 1])
            except Exception:
                continue

        logger.debug("Could not read function object '%s'", func_name)
        return float("nan")

    def _read_stage_torque(self, stage_name: str) -> float:
        """Extract Mz (torque around axis) for a stage from forces function object."""
        func_name = f"forces_{stage_name}"
        if not self._pp_dir.exists():
            return float("nan")

        for dat_file in self._pp_dir.rglob(f"{func_name}/**/*.dat"):
            try:
                lines = [
                    line.strip()
                    for line in dat_file.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
                if not lines:
                    continue
                values = [
                    float(v)
                    for v in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", lines[-1])
                ]
                # OpenFOAM forces format:
                # time, force_p(3), force_v(3), moment_p(3), moment_v(3)
                if len(values) >= 13:
                    return float(values[9] + values[12])
            except Exception:
                continue
        return float("nan")

    def _find_solver_log(self) -> Path | None:
        candidates = [
            self.case_dir / "log.simpleFoam",
            self.case_dir / "log.pimpleFoam",
            self.case_dir / "log.rhoSimpleFoam",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Search generically
        logs = list(self.case_dir.glob("log.*"))
        if logs:
            return max(logs, key=lambda p: p.stat().st_mtime)
        return None


# ---------------------------------------------------------------------------
# Log parsing helpers
# ---------------------------------------------------------------------------


def _count_time_steps(log_text: str) -> int:
    matches = re.findall(r"^Time = ([\d.]+)s?", log_text, re.MULTILINE)
    return int(float(matches[-1])) if matches else 0


def _extract_residual_history(log_text: str) -> dict[str, list[float]]:
    """Extract per-field residual arrays from a solver log."""
    history: dict[str, list[float]] = {}
    pattern = re.compile(r"Solving for (\w+),.*?Final residual = ([\d.eE+\-]+)")
    for m in pattern.finditer(log_text):
        fname = m.group(1)
        val = float(m.group(2))
        history.setdefault(fname, []).append(val)
    return history


def _safe_float(v: float) -> float | None:
    """Convert nan to None for JSON serialization."""
    if math.isnan(v):
        return None
    return v
