"""
fan_cfd.optimization.optimizer
================================
Optimizer implementations for fan design optimization.

Optimizers modify blade geometry parameters and re-run CFD to find
configurations that maximize the objective function.

Design variables
----------------
- blade_count per rotor stage
- chord_profile constant value (scale)
- twist_profile constant value at root and tip
- hub_diameter_m
- duct total_length_m (if duct enabled)
- axial stage positions (multi-stage)
"""

from __future__ import annotations

import copy
import csv
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from fan_cfd.optimization.objective import score_design
from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import FanCFDConfig
    from fan_cfd.openfoam.postprocess import FanPerformance

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    """Outcome of one optimization trial."""

    trial_id: int
    config_hash: str
    score: float
    performance: "FanPerformance | None"
    design_variables: dict[str, float] = field(default_factory=dict)
    error: str = ""

    @property
    def valid(self) -> bool:
        return self.performance is not None and not self.error


@dataclass
class OptimizationResult:
    """Summary of a complete optimization run."""

    best_trial: TrialResult | None = None
    all_trials: list[TrialResult] = field(default_factory=list)
    n_trials: int = 0
    method: str = "random"


# ---------------------------------------------------------------------------
# Base optimizer
# ---------------------------------------------------------------------------


class FanOptimizer:
    """
    Base class for fan design optimizers.

    Subclasses implement ``suggest_next()``.
    """

    def __init__(
        self,
        base_config: "FanCFDConfig",
        n_trials: int,
        output_dir: Path,
    ) -> None:
        self.base_config = base_config
        self.n_trials = n_trials
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[TrialResult] = []

    def run(self) -> OptimizationResult:
        """Run the full optimization loop."""
        logger.info(
            "Starting optimization: %d trials, method=%s",
            self.n_trials,
            self.__class__.__name__,
        )

        for i in range(self.n_trials):
            logger.info("--- Trial %d/%d ---", i + 1, self.n_trials)
            trial_config = self.suggest_next(self.history)
            trial_result = self.run_trial(trial_config, i)
            self.history.append(trial_result)
            self.save_leaderboard(self.history)

            if trial_result.valid:
                logger.info(
                    "Trial %d: score=%.4f  eff=%.3f  dP=%.1f Pa  Q=%.4f m³/s",
                    i,
                    trial_result.score,
                    trial_result.performance.efficiency if trial_result.performance else float("nan"),
                    trial_result.performance.pressure_rise_pa if trial_result.performance else float("nan"),
                    trial_result.performance.flow_rate_m3_s if trial_result.performance else float("nan"),
                )

        best = max((t for t in self.history if t.valid), key=lambda t: t.score, default=None)
        return OptimizationResult(
            best_trial=best,
            all_trials=self.history,
            n_trials=self.n_trials,
            method=self.__class__.__name__,
        )

    def suggest_next(self, history: list[TrialResult]) -> "FanCFDConfig":
        """Return a new config to evaluate. Subclasses override this."""
        raise NotImplementedError

    def run_trial(self, config: "FanCFDConfig", trial_id: int) -> TrialResult:
        """Run CFD for one trial config and return scored result."""
        import hashlib

        from fan_cfd.geometry.fan_geometry import build_and_export_geometry
        from fan_cfd.openfoam.case_builder import OpenFoamCaseBuilder
        from fan_cfd.openfoam.postprocess import PostProcessor
        from fan_cfd.openfoam.runner import OpenFoamRunner

        trial_dir = self.output_dir / f"trial_{trial_id:04d}"
        trial_dir.mkdir(exist_ok=True)

        config_str = json.dumps(config.model_dump(), sort_keys=True, default=str)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

        dvars = _extract_design_variables(config)

        try:
            # Geometry
            geom_dir = trial_dir / "geometry"
            stl_paths = build_and_export_geometry(config, geom_dir)

            # Case
            case_dir = trial_dir / "openfoam"
            builder = OpenFoamCaseBuilder(config, case_dir)
            builder.build(stl_paths)

            # Run
            runner = OpenFoamRunner(case_dir, config.cfd)
            run_result = runner.run_full_pipeline()
            if not run_result.success:
                raise RuntimeError(run_result.error_message or "OpenFOAM pipeline failed")

            # Postprocess
            pp = PostProcessor(case_dir, config.fan)
            perf = pp.extract_all()
            pp.save_results(perf, trial_dir / "results.json")

            score = score_design(perf, config.objective)
            return TrialResult(
                trial_id=trial_id,
                config_hash=config_hash,
                score=score,
                performance=perf,
                design_variables=dvars,
            )

        except Exception as exc:
            logger.error("Trial %d failed: %s", trial_id, exc)
            return TrialResult(
                trial_id=trial_id,
                config_hash=config_hash,
                score=-9999.0,
                performance=None,
                design_variables=dvars,
                error=str(exc),
            )

    def save_leaderboard(self, results: list[TrialResult]) -> None:
        """Write CSV leaderboard sorted by score."""
        lb_path = self.output_dir / "leaderboard.csv"
        sorted_results = sorted(results, key=lambda t: t.score, reverse=True)

        with open(lb_path, "w", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "rank", "trial_id", "score", "efficiency", "pressure_rise_pa",
                    "flow_rate_m3_s", "torque_nm", "valid", "error",
                ] + list(sorted_results[0].design_variables.keys() if sorted_results else []),
            )
            writer.writeheader()
            for rank, t in enumerate(sorted_results, 1):
                row: dict = {
                    "rank": rank,
                    "trial_id": t.trial_id,
                    "score": round(t.score, 6),
                    "efficiency": _fmt(t.performance.efficiency if t.performance else float("nan")),
                    "pressure_rise_pa": _fmt(t.performance.pressure_rise_pa if t.performance else float("nan")),
                    "flow_rate_m3_s": _fmt(t.performance.flow_rate_m3_s if t.performance else float("nan")),
                    "torque_nm": _fmt(t.performance.torque_nm if t.performance else float("nan")),
                    "valid": t.valid,
                    "error": t.error[:80] if t.error else "",
                }
                row.update(t.design_variables)
                writer.writerow(row)

        logger.debug("Leaderboard saved: %s", lb_path)


# ---------------------------------------------------------------------------
# Random search
# ---------------------------------------------------------------------------


class RandomSearchOptimizer(FanOptimizer):
    """Uniform random sampling of the design space."""

    # Design variable bounds
    BOUNDS: dict[str, tuple[float, float]] = {
        "blade_count": (3, 12),
        "chord_scale": (0.5, 2.0),
        "twist_root_deg": (10.0, 60.0),
        "twist_tip_deg": (5.0, 45.0),
        "hub_diameter_scale": (0.8, 1.2),
    }

    def suggest_next(self, history: list[TrialResult]) -> "FanCFDConfig":
        config = copy.deepcopy(self.base_config)
        dvars: dict[str, float] = {}

        for stage in config.fan.stages:
            from fan_cfd.config import StageType

            if stage.type == StageType.ROTOR:
                bc = int(random.uniform(*self.BOUNDS["blade_count"]))
                object.__setattr__(stage, "blade_count", bc)
                dvars[f"{stage.name}_blade_count"] = bc

                chord_scale = random.uniform(*self.BOUNDS["chord_scale"])
                twist_root = random.uniform(*self.BOUNDS["twist_root_deg"])
                twist_tip = random.uniform(*self.BOUNDS["twist_tip_deg"])
                dvars[f"{stage.name}_chord_scale"] = chord_scale
                dvars[f"{stage.name}_twist_root"] = twist_root
                dvars[f"{stage.name}_twist_tip"] = twist_tip

                from fan_cfd.config import BladeConfig, Profile

                new_blade = BladeConfig(
                    airfoil=stage.blade.airfoil,
                    radial_sections=stage.blade.radial_sections,
                    chord_profile=Profile.linear(
                        interpolate_chord(stage.blade.chord_profile, 0.0) * chord_scale,
                        interpolate_chord(stage.blade.chord_profile, 1.0) * chord_scale,
                    ),
                    twist_profile_deg=Profile.linear(twist_root, twist_tip),
                    thickness_scale=stage.blade.thickness_scale,
                )
                object.__setattr__(stage, "blade", new_blade)

        return config


# ---------------------------------------------------------------------------
# Differential evolution
# ---------------------------------------------------------------------------


class DifferentialEvolutionOptimizer(FanOptimizer):
    """
    Simple differential evolution over a flat real-valued parameter vector.

    DE parameters: F=0.8 (mutation), CR=0.9 (crossover), pop_size=10.
    """

    F = 0.8   # mutation factor
    CR = 0.9  # crossover rate
    POP_SIZE = 8

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._population: list[np.ndarray] | None = None
        self._pop_scores: list[float] | None = None
        self._trial_idx = 0

    def suggest_next(self, history: list[TrialResult]) -> "FanCFDConfig":
        bounds_list = self._get_bounds_list()
        n_dims = len(bounds_list)
        lo = np.array([b[0] for b in bounds_list])
        hi = np.array([b[1] for b in bounds_list])

        # Initialize population on first call
        if self._population is None:
            pop: list[np.ndarray] = []
            for _ in range(self.POP_SIZE):
                pop.append(lo + np.random.rand(n_dims) * (hi - lo))
            self._population = pop
            self._pop_scores = [float("-inf")] * self.POP_SIZE

        # Update scores from history
        if history:
            pop_trials = history[-self.POP_SIZE:]
            for i, t in enumerate(pop_trials):
                if i < len(self._pop_scores) and t.valid:
                    self._pop_scores[i] = t.score

        # Generate candidate via DE/rand/1/bin mutation
        pop = self._population
        i = self._trial_idx % self.POP_SIZE
        self._trial_idx += 1

        candidates = [j for j in range(self.POP_SIZE) if j != i]
        a, b_, c = random.sample(candidates, min(3, len(candidates))) if len(candidates) >= 3 else (0, 0, 0)
        mutant = np.clip(pop[a] + self.F * (pop[b_] - pop[c]), lo, hi)

        trial_vec = np.where(np.random.rand(n_dims) < self.CR, mutant, pop[i])

        # Accept if better than target (greedy selection)
        # We'll update after the trial runs — for now use trial_vec
        return self._vec_to_config(trial_vec, bounds_list)

    def _get_bounds_list(self) -> list[tuple[float, float]]:
        from fan_cfd.config import StageType
        bounds = []
        for stage in self.base_config.fan.stages:
            if stage.type == StageType.ROTOR:
                bounds += [(3, 12), (0.5, 2.0), (10.0, 60.0), (5.0, 45.0)]
        return bounds

    def _vec_to_config(self, vec: np.ndarray, bounds: list) -> "FanCFDConfig":
        from fan_cfd.config import BladeConfig, Profile, StageType

        config = copy.deepcopy(self.base_config)
        idx = 0
        for stage in config.fan.stages:
            if stage.type == StageType.ROTOR:
                bc = int(round(vec[idx]))
                chord_scale = vec[idx + 1]
                twist_root = vec[idx + 2]
                twist_tip = vec[idx + 3]
                idx += 4

                object.__setattr__(stage, "blade_count", max(2, min(20, bc)))
                new_blade = BladeConfig(
                    airfoil=stage.blade.airfoil,
                    radial_sections=stage.blade.radial_sections,
                    chord_profile=Profile.linear(
                        interpolate_chord(stage.blade.chord_profile, 0.0) * chord_scale,
                        interpolate_chord(stage.blade.chord_profile, 1.0) * chord_scale,
                    ),
                    twist_profile_deg=Profile.linear(twist_root, twist_tip),
                    thickness_scale=stage.blade.thickness_scale,
                )
                object.__setattr__(stage, "blade", new_blade)
        return config


# ---------------------------------------------------------------------------
# Placeholder optimizers
# ---------------------------------------------------------------------------


class BayesianOptimizer(FanOptimizer):
    """
    Placeholder for Bayesian optimization (e.g. via scikit-optimize or botorch).
    Falls back to random search until implemented.
    """

    def suggest_next(self, history: list[TrialResult]) -> "FanCFDConfig":
        logger.warning("BayesianOptimizer not yet implemented; falling back to random search.")
        return RandomSearchOptimizer(
            self.base_config, self.n_trials, self.output_dir
        ).suggest_next(history)


class GeneticAlgorithmOptimizer(FanOptimizer):
    """
    Placeholder for genetic algorithm optimization.
    Falls back to random search until implemented.
    """

    def suggest_next(self, history: list[TrialResult]) -> "FanCFDConfig":
        logger.warning("GeneticAlgorithmOptimizer not yet implemented; falling back to random search.")
        return RandomSearchOptimizer(
            self.base_config, self.n_trials, self.output_dir
        ).suggest_next(history)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_design_variables(config: "FanCFDConfig") -> dict[str, float]:
    """Extract key design variables from a config for logging."""
    from fan_cfd.config import StageType
    from fan_cfd.geometry.blade_profiles import interpolate_profile

    dvars: dict[str, float] = {}
    dvars["hub_diameter_m"] = config.fan.hub_diameter_m
    for stage in config.fan.stages:
        if stage.type == StageType.ROTOR:
            dvars[f"{stage.name}_blade_count"] = stage.blade_count
            dvars[f"{stage.name}_chord_tip"] = interpolate_profile(stage.blade.chord_profile, 1.0)
            dvars[f"{stage.name}_twist_root_deg"] = interpolate_profile(stage.blade.twist_profile_deg, 0.0)
            dvars[f"{stage.name}_twist_tip_deg"] = interpolate_profile(stage.blade.twist_profile_deg, 1.0)
    return dvars


def interpolate_chord(profile, r_norm: float) -> float:
    from fan_cfd.geometry.blade_profiles import interpolate_profile
    try:
        return interpolate_profile(profile, r_norm)
    except Exception:
        return 0.03


def _fmt(v: float) -> str:
    if math.isnan(v):
        return "nan"
    return f"{v:.6g}"


# ---------------------------------------------------------------------------
# Solver backend abstraction
# ---------------------------------------------------------------------------


class SolverBackend:
    name: str = "base"
    description: str = "Base solver backend"

    def check_available(self) -> bool:
        return False

    def run(self, case_dir: Path, config) -> object:
        raise NotImplementedError


class OpenFoamContinuumBackend(SolverBackend):
    name = "openfoam_continuum"
    description = "OpenFOAM RANS steady/transient, continuum flow (simpleFoam/pimpleFoam + MRF/AMI)"

    def check_available(self) -> bool:
        import shutil
        return shutil.which("simpleFoam") is not None

    def run(self, case_dir: Path, config) -> object:
        from fan_cfd.openfoam.runner import OpenFoamRunner
        runner = OpenFoamRunner(case_dir, config.cfd)
        return runner.run_full_pipeline()


class RarefiedFlowBackend(SolverBackend):
    name = "rarefied_flow"
    description = (
        "Placeholder: DSMC or molecular-flow solver for low-pressure/high-Kn regimes "
        "(e.g. turbomolecular pumps). Not yet implemented."
    )

    def check_available(self) -> bool:
        return False

    def run(self, case_dir: Path, config) -> object:
        raise NotImplementedError(
            "Rarefied flow (DSMC/molecular) solver backend is not yet implemented. "
            "For turbomolecular pump simulation, consider dsmcFoam+ or SPARTA."
        )
