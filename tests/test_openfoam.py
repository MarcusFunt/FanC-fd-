"""
tests/test_openfoam.py
=======================
Tests for OpenFOAM dict generation, MRF zones, and log parsing.
"""

import re
import tempfile
from pathlib import Path

import pytest

from fan_cfd.config import (
    BoundaryConfig,
    BladeConfig,
    CFDConfig,
    FanCFDConfig,
    FanConfig,
    FluidConfig,
    MeshConfig,
    Profile,
    RunConfig,
    StageConfig,
    StageType,
)
from fan_cfd.openfoam.dict_writer import (
    write_block_mesh_dict,
    write_boundary_condition_U,
    write_boundary_condition_k,
    write_boundary_condition_omega,
    write_boundary_condition_p,
    write_control_dict,
    write_decompose_par_dict,
    write_foam_header,
    write_fv_schemes,
    write_fv_solution,
    write_snappy_hex_mesh_dict,
    write_transport_properties,
    write_turbulence_properties,
)
from fan_cfd.openfoam.mrf_zones import MRFZone, build_mrf_zones, write_mrf_properties
from fan_cfd.openfoam.runner import _parse_check_mesh_log, _parse_solver_log

SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cfd_config() -> CFDConfig:
    return CFDConfig(
        solver="simpleFoam",
        turbulence_model="kOmegaSST",
        inlet=BoundaryConfig(velocity_m_s=5.0, turbulence_intensity=0.05, hydraulic_diameter_m=0.12),
        outlet=BoundaryConfig(patch_name="outlet", velocity_m_s=5.0),
        fluid=FluidConfig(nu_m2_s=1.5e-5),
        mesh=MeshConfig(base_cell_size_m=0.005, refinement_levels=3, boundary_layers=5),
        run=RunConfig(n_iterations=500, write_interval=100),
    )


def _make_fan_config(n_rotors: int = 1) -> FanConfig:
    stages = []
    for i in range(n_rotors * 2):
        stype = StageType.ROTOR if i % 2 == 0 else StageType.STATOR
        stages.append(
            StageConfig(
                name=f"{'rotor' if stype == StageType.ROTOR else 'stator'}_{i // 2 + 1}",
                type=stype,
                axial_position_m=i * 0.04,
                blade_count=5,
                rpm=5000.0 if stype == StageType.ROTOR else None,
                blade=BladeConfig(
                    chord_profile=Profile.constant(0.025),
                    twist_profile_deg=Profile.constant(30.0),
                ),
            )
        )
    return FanConfig(
        name="test",
        max_diameter_m=0.12,
        hub_diameter_m=0.03,
        rpm=5000.0,
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Foam header
# ---------------------------------------------------------------------------


class TestFoamHeader:
    def test_contains_class_name(self):
        h = write_foam_header("dictionary", "blockMeshDict", "system")
        assert "dictionary" in h
        assert "blockMeshDict" in h

    def test_contains_version(self):
        h = write_foam_header("volScalarField", "p")
        assert "version" in h
        assert "2.0" in h

    def test_with_location(self):
        h = write_foam_header("dictionary", "fvSchemes", "system")
        assert 'location' in h
        assert '"system"' in h


# ---------------------------------------------------------------------------
# blockMeshDict
# ---------------------------------------------------------------------------


class TestBlockMeshDict:
    def test_contains_vertices(self):
        cfg = _make_cfd_config()
        fan = _make_fan_config()
        text = write_block_mesh_dict(cfg, fan)
        assert "vertices" in text

    def test_contains_inlet_outlet(self):
        cfg = _make_cfd_config()
        fan = _make_fan_config()
        text = write_block_mesh_dict(cfg, fan)
        assert "inlet" in text
        assert "outlet" in text

    def test_contains_blocks(self):
        cfg = _make_cfd_config()
        fan = _make_fan_config()
        text = write_block_mesh_dict(cfg, fan)
        assert "blocks" in text
        assert "hex" in text


# ---------------------------------------------------------------------------
# MRF zones
# ---------------------------------------------------------------------------


class TestMRFZones:
    def test_single_rotor_gives_one_zone(self):
        fan = _make_fan_config(n_rotors=1)
        zones = build_mrf_zones(fan)
        assert len(zones) == 1

    def test_two_rotors_give_two_zones(self):
        fan = _make_fan_config(n_rotors=2)
        zones = build_mrf_zones(fan)
        assert len(zones) == 2

    def test_zone_omega_matches_rpm(self):
        import math
        fan = _make_fan_config(n_rotors=1)
        zones = build_mrf_zones(fan)
        expected_omega = 5000.0 * 2 * math.pi / 60.0
        assert abs(zones[0].omega_rad_s - expected_omega) < 1e-3

    def test_mrf_properties_written(self):
        fan = _make_fan_config(n_rotors=1)
        zones = build_mrf_zones(fan)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "MRFProperties"
            write_mrf_properties(zones, out)
            assert out.exists()
            text = out.read_text()
            assert "omega" in text
            assert "rotor_1_MRF" in text

    def test_multi_stage_mrf_zone_count(self):
        """4-stage config with 2 rotors should produce 2 MRF zones."""
        fan = _make_fan_config(n_rotors=2)
        zones = build_mrf_zones(fan)
        assert len(zones) == 2


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


class TestBoundaryConditions:
    def test_U_has_inlet_velocity(self):
        cfg = _make_cfd_config()
        text = write_boundary_condition_U(cfg)
        assert "5.0" in text or "5.0000" in text
        assert "inlet" in text
        assert "outlet" in text

    def test_p_has_zero_gradient_inlet(self):
        cfg = _make_cfd_config()
        text = write_boundary_condition_p(cfg)
        assert "zeroGradient" in text
        assert "inlet" in text

    def test_k_has_turbulence_intensity(self):
        cfg = _make_cfd_config()
        text = write_boundary_condition_k(cfg)
        assert "0.05" in text or "turbulentIntensityKineticEnergyInlet" in text

    def test_omega_has_wall_function(self):
        cfg = _make_cfd_config()
        text = write_boundary_condition_omega(cfg)
        assert "omegaWallFunction" in text

    def test_nut_has_wall_function(self):
        cfg = _make_cfd_config()
        text = write_boundary_condition_nut(cfg)
        assert "nutkWallFunction" in text


# ---------------------------------------------------------------------------
# controlDict
# ---------------------------------------------------------------------------


class TestControlDict:
    def test_application_name(self):
        cfg = _make_cfd_config()
        text = write_control_dict(cfg)
        assert "simpleFoam" in text

    def test_end_time(self):
        cfg = _make_cfd_config()
        text = write_control_dict(cfg)
        assert "500" in text  # n_iterations

    def test_write_interval(self):
        cfg = _make_cfd_config()
        text = write_control_dict(cfg)
        assert "100" in text  # write_interval


# ---------------------------------------------------------------------------
# decomposeParDict
# ---------------------------------------------------------------------------


class TestDecomposeParDict:
    def test_n_procs(self):
        text = write_decompose_par_dict(8)
        assert "8" in text
        assert "scotch" in text


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------


class TestLogParsing:
    def test_parse_checkmesh_log(self):
        log_path = SAMPLE_DATA / "sample_checkMesh.log"
        if not log_path.exists():
            pytest.skip("Sample log not found")
        text = log_path.read_text()
        result = _parse_check_mesh_log(text)
        assert result.passed is True
        assert result.n_cells == 120340
        assert result.max_non_ortho == pytest.approx(41.23)
        assert result.max_skewness == pytest.approx(1.74)

    def test_parse_simplefoam_log(self):
        log_path = SAMPLE_DATA / "sample_simpleFoam.log"
        if not log_path.exists():
            pytest.skip("Sample log not found")
        text = log_path.read_text()
        result = _parse_solver_log(text, elapsed=521.7)
        assert result.diverged is False
        assert result.n_iterations == 500
        assert "Ux" in result.final_residuals
        assert result.final_residuals["Ux"] < 1e-4

    def test_diverged_log_detected(self):
        diverged_log = """
Time = 100
FOAM FATAL ERROR: Maximum number of iterations exceeded
"""
        result = _parse_solver_log(diverged_log, elapsed=1.0)
        assert result.diverged is True
