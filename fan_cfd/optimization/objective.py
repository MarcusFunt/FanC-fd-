"""
fan_cfd.optimization.objective
================================
Objective function and penalty calculator for fan design optimization.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fan_cfd.config import ObjectiveConfig
    from fan_cfd.openfoam.postprocess import FanPerformance


# ---------------------------------------------------------------------------
# Penalty calculator
# ---------------------------------------------------------------------------


class PenaltyCalculator:
    """
    Computes a scalar penalty for constraint violations.

    Constraints are expressed as ``{metric_name: max_allowed_value}``
    or ``{metric_name: min_required_value}`` (sign conventions below).
    """

    # Constraint names and their sense (True = upper bound, False = lower bound)
    _UPPER_BOUNDS = {
        "max_non_ortho": 70.0,
        "max_skewness": 4.0,
        "shaft_power_w": math.inf,
    }
    _LOWER_BOUNDS = {
        "efficiency": 0.0,
        "pressure_rise_pa": 0.0,
        "flow_rate_m3_s": 0.0,
    }

    def compute_penalty(
        self,
        result: "FanPerformance",
        constraints: dict[str, float],
    ) -> float:
        """
        Compute total penalty for constraint violations.

        Returns a non-negative penalty value. 0 = no violations.

        Parameters
        ----------
        result : FanPerformance
        constraints : dict[str, float]
            Custom constraint thresholds from ObjectiveConfig.
        """
        penalty = 0.0

        # Mesh failed (no cells)
        if result.mesh.n_cells == 0:
            penalty += 1000.0

        # Solver diverged
        if not result.convergence.converged and result.convergence.n_iterations > 0:
            penalty += 500.0

        # NaN results
        for attr in ("pressure_rise_pa", "flow_rate_m3_s", "torque_nm", "efficiency"):
            val = getattr(result, attr)
            if math.isnan(val):
                penalty += 200.0

        # User-defined constraints
        value_map = {
            "efficiency": result.efficiency,
            "pressure_rise_pa": result.pressure_rise_pa,
            "flow_rate_m3_s": result.flow_rate_m3_s,
            "shaft_power_w": result.shaft_power_w,
            "max_non_ortho": result.mesh.max_non_ortho,
        }

        for name, threshold in constraints.items():
            val = value_map.get(name, float("nan"))
            if math.isnan(val):
                penalty += 100.0
                continue

            # Convention: if threshold > 0, it's a minimum; if negative, upper bound
            # Or use prefixes: 'min_' and 'max_' in key name
            if name.startswith("min_"):
                bare = name[4:]
                actual = value_map.get(bare, float("nan"))
                if not math.isnan(actual) and actual < threshold:
                    penalty += (threshold - actual) / max(abs(threshold), 1.0) * 100.0
            elif name.startswith("max_"):
                bare = name[4:]
                actual = value_map.get(bare, float("nan"))
                if not math.isnan(actual) and actual > threshold:
                    penalty += (actual - threshold) / max(abs(threshold), 1.0) * 100.0
            else:
                # Default: treat as minimum
                if not math.isnan(val) and val < threshold:
                    penalty += (threshold - val) / max(abs(threshold), 1.0) * 100.0

        return penalty


# ---------------------------------------------------------------------------
# Score function
# ---------------------------------------------------------------------------


def score_design(
    result: "FanPerformance",
    objective: "ObjectiveConfig",
) -> float:
    """
    Return a scalar score for a completed CFD result. Higher is better.

    For single-objective mode:
    - efficiency:     score = efficiency (0–1) - penalty
    - pressure_rise:  score = pressure_rise_pa / 1000 - penalty (normalized)
    - flow_rate:      score = flow_rate_m3_s * 1000 - penalty

    For multi_objective mode:
    - Weighted sum over metrics (weights from objective.weights).
    """
    calculator = PenaltyCalculator()
    penalty = calculator.compute_penalty(result, objective.constraints)

    if objective.mode == "multi_objective":
        return _multi_objective_score(result, objective) - penalty

    # Single objective
    maximize = objective.maximize
    raw = _get_metric(result, maximize)
    if math.isnan(raw):
        return -1000.0 - penalty

    # Normalize to a reasonable scale (roughly 0–10)
    if maximize == "efficiency":
        normalized = raw  # already 0–1
    elif maximize == "pressure_rise":
        normalized = raw / 1000.0  # Pa → kPa scale
    elif maximize == "flow_rate":
        normalized = raw * 1000.0  # m³/s → L/s scale
    else:
        normalized = raw

    return normalized - penalty


def _get_metric(result: "FanPerformance", name: str) -> float:
    metric_map = {
        "efficiency": result.efficiency,
        "pressure_rise": result.pressure_rise_pa,
        "pressure_rise_pa": result.pressure_rise_pa,
        "flow_rate": result.flow_rate_m3_s,
        "flow_rate_m3_s": result.flow_rate_m3_s,
        "shaft_power_w": result.shaft_power_w,
    }
    return metric_map.get(name, float("nan"))


def _multi_objective_score(
    result: "FanPerformance",
    objective: "ObjectiveConfig",
) -> float:
    """Weighted normalized sum of objectives."""
    weights = objective.weights or {"efficiency": 0.6, "pressure_rise": 0.4}
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    score = 0.0
    for metric, weight in weights.items():
        val = _get_metric(result, metric)
        if math.isnan(val):
            continue
        # Normalize each metric to ~[0,1]
        if metric == "efficiency":
            norm = val
        elif metric in ("pressure_rise", "pressure_rise_pa"):
            norm = val / 1000.0
        elif metric in ("flow_rate", "flow_rate_m3_s"):
            norm = val * 1000.0
        else:
            norm = val
        score += weight / total_weight * norm

    return score
