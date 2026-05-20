"""
tests/test_optimization.py
===========================
Tests for the optimization objective, scoring, and optimizer infrastructure.
"""

import csv
import math
import tempfile
from pathlib import Path

from fan_cfd.config import ObjectiveConfig
from fan_cfd.openfoam.postprocess import (
    ConvergenceResult,
    FanPerformance,
    MeshQuality,
)
from fan_cfd.optimization.objective import PenaltyCalculator, score_design


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_perf(
    efficiency=0.5,
    pressure_rise=50.0,
    flow_rate=0.03,
    torque=0.01,
    converged=True,
    n_cells=100000,
) -> FanPerformance:
    perf = FanPerformance()
    perf.efficiency = efficiency
    perf.pressure_rise_pa = pressure_rise
    perf.flow_rate_m3_s = flow_rate
    perf.torque_nm = torque
    perf.shaft_power_w = torque * (5000 * 2 * math.pi / 60)
    perf.mesh = MeshQuality(ok=True, n_cells=n_cells, max_non_ortho=35.0, max_skewness=1.5)
    perf.convergence = ConvergenceResult(
        converged=converged,
        n_iterations=500,
        final_residuals={"Ux": 1e-5, "p": 2e-6},
    )
    return perf


def _make_failed_perf() -> FanPerformance:
    perf = FanPerformance()
    perf.efficiency = float("nan")
    perf.pressure_rise_pa = float("nan")
    perf.flow_rate_m3_s = float("nan")
    perf.torque_nm = float("nan")
    perf.shaft_power_w = float("nan")
    perf.mesh = MeshQuality(ok=False, n_cells=0)
    perf.convergence = ConvergenceResult(converged=False)
    return perf


# ---------------------------------------------------------------------------
# PenaltyCalculator
# ---------------------------------------------------------------------------


class TestPenaltyCalculator:
    def test_no_penalty_for_good_result(self):
        calc = PenaltyCalculator()
        perf = _make_perf()
        penalty = calc.compute_penalty(perf, {})
        assert penalty == 0.0

    def test_penalty_for_zero_cells(self):
        calc = PenaltyCalculator()
        perf = _make_failed_perf()
        penalty = calc.compute_penalty(perf, {})
        assert penalty >= 1000.0

    def test_penalty_for_nan_efficiency(self):
        calc = PenaltyCalculator()
        perf = _make_perf()
        perf.efficiency = float("nan")
        penalty = calc.compute_penalty(perf, {})
        assert penalty > 0.0

    def test_custom_min_constraint_violated(self):
        calc = PenaltyCalculator()
        perf = _make_perf(pressure_rise=5.0)  # below threshold
        penalty = calc.compute_penalty(perf, {"min_pressure_rise_pa": 30.0})
        assert penalty > 0.0

    def test_custom_min_constraint_satisfied(self):
        calc = PenaltyCalculator()
        perf = _make_perf(pressure_rise=50.0)  # above threshold
        penalty = calc.compute_penalty(perf, {"min_pressure_rise_pa": 30.0})
        assert penalty == 0.0

    def test_non_converged_adds_penalty(self):
        calc = PenaltyCalculator()
        perf = _make_perf(converged=False)
        penalty = calc.compute_penalty(perf, {})
        assert penalty > 0.0


# ---------------------------------------------------------------------------
# score_design
# ---------------------------------------------------------------------------


class TestScoreDesign:
    def test_higher_efficiency_gives_higher_score(self):
        obj = ObjectiveConfig(mode="single", maximize="efficiency")
        perf_low = _make_perf(efficiency=0.3)
        perf_high = _make_perf(efficiency=0.7)
        score_low = score_design(perf_low, obj)
        score_high = score_design(perf_high, obj)
        assert score_high > score_low

    def test_failed_mesh_gives_very_negative_score(self):
        obj = ObjectiveConfig(mode="single", maximize="efficiency")
        perf = _make_failed_perf()
        score = score_design(perf, obj)
        assert score < -500.0

    def test_pressure_rise_objective(self):
        obj = ObjectiveConfig(mode="single", maximize="pressure_rise")
        perf_low = _make_perf(pressure_rise=10.0)
        perf_high = _make_perf(pressure_rise=100.0)
        s_low = score_design(perf_low, obj)
        s_high = score_design(perf_high, obj)
        assert s_high > s_low

    def test_flow_rate_objective(self):
        obj = ObjectiveConfig(mode="single", maximize="flow_rate")
        perf_low = _make_perf(flow_rate=0.01)
        perf_high = _make_perf(flow_rate=0.05)
        s_low = score_design(perf_low, obj)
        s_high = score_design(perf_high, obj)
        assert s_high > s_low

    def test_multi_objective_score(self):
        obj = ObjectiveConfig(
            mode="multi_objective",
            maximize="efficiency",
            weights={"efficiency": 0.6, "pressure_rise": 0.4},
        )
        perf = _make_perf(efficiency=0.5, pressure_rise=50.0)
        score = score_design(perf, obj)
        assert not math.isnan(score)
        assert score > -100.0

    def test_constraint_violation_reduces_score(self):
        obj_with = ObjectiveConfig(
            mode="single",
            maximize="efficiency",
            constraints={"min_pressure_rise_pa": 200.0},  # impossible to meet
        )
        obj_without = ObjectiveConfig(mode="single", maximize="efficiency")
        perf = _make_perf(pressure_rise=50.0)
        s_with = score_design(perf, obj_with)
        s_without = score_design(perf, obj_without)
        assert s_without > s_with


# ---------------------------------------------------------------------------
# Leaderboard CSV
# ---------------------------------------------------------------------------


class TestLeaderboard:
    def test_leaderboard_written_correctly(self):
        """Test that save_leaderboard produces a valid CSV."""
        from fan_cfd.config import (
            BladeConfig,
            FanCFDConfig,
            FanConfig,
            Profile,
            StageConfig,
            StageType,
        )
        from fan_cfd.optimization.optimizer import (
            FanOptimizer,
            TrialResult,
        )

        # Minimal FanCFDConfig for optimizer construction
        stage = StageConfig(
            name="rotor_1",
            type=StageType.ROTOR,
            axial_position_m=0.0,
            blade_count=5,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile.constant(0.025),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )
        fan = FanConfig(
            name="test", max_diameter_m=0.12, hub_diameter_m=0.03, rpm=5000.0, stages=[stage]
        )
        config = FanCFDConfig(fan=fan)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            class MockOptimizer(FanOptimizer):
                def suggest_next(self, history):
                    return self.base_config

            opt = MockOptimizer(config, n_trials=3, output_dir=out_dir)

            trials = [
                TrialResult(
                    trial_id=0,
                    config_hash="abc",
                    score=0.45,
                    performance=_make_perf(efficiency=0.45),
                    design_variables={"rotor_1_blade_count": 5},
                ),
                TrialResult(
                    trial_id=1,
                    config_hash="def",
                    score=0.62,
                    performance=_make_perf(efficiency=0.62),
                    design_variables={"rotor_1_blade_count": 7},
                ),
            ]

            opt.save_leaderboard(trials)
            lb_path = out_dir / "leaderboard.csv"
            assert lb_path.exists()

            with open(lb_path) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)

            assert len(rows) == 2
            # Rows should be sorted by score descending
            assert float(rows[0]["score"]) >= float(rows[1]["score"])
            # Rank 1 should be the best
            assert rows[0]["rank"] == "1"
