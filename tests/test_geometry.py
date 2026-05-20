"""
tests/test_geometry.py
=======================
Tests for 3D blade and assembly geometry generation.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import trimesh

from fan_cfd.config import (
    BladeConfig,
    DuctConfig,
    FanCFDConfig,
    FanConfig,
    Profile,
    ProfileType,
    StageConfig,
    StageType,
)
from fan_cfd.geometry.assembly_geometry import generate_duct, generate_full_assembly, generate_hub
from fan_cfd.geometry.cad_export import (
    export_stl_files,
    is_3d_printable_mesh,
    validate_stl_files,
)
from fan_cfd.geometry.fan_geometry import build_geometry
from fan_cfd.geometry.stage_geometry import generate_stage_geometry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_simple_fan(blade_count: int = 5, n_stages: int = 1) -> FanConfig:
    stages = []
    for i in range(n_stages):
        stage_type = StageType.ROTOR if i % 2 == 0 else StageType.STATOR
        stages.append(
            StageConfig(
                name=f"{'rotor' if stage_type == StageType.ROTOR else 'stator'}_{i+1}",
                type=stage_type,
                axial_position_m=i * 0.04,
                blade_count=blade_count,
                rpm=5000.0 if stage_type == StageType.ROTOR else None,
                blade=BladeConfig(
                    airfoil="naca4412",
                    radial_sections=5,
                    chord_profile=Profile.constant(0.025),
                    twist_profile_deg=Profile.linear(40.0, 20.0),
                ),
            )
        )
    return FanConfig(
        name="test_fan",
        max_diameter_m=0.12,
        hub_diameter_m=0.03,
        rpm=5000.0,
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Stage geometry
# ---------------------------------------------------------------------------


class TestStageGeometry:
    def test_correct_blade_count(self):
        fan = _make_simple_fan(blade_count=5)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        assert len(blades) == 5

    def test_blade_count_7(self):
        fan = _make_simple_fan(blade_count=7)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        assert len(blades) == 7

    def test_each_blade_is_trimesh(self):
        fan = _make_simple_fan(blade_count=3)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        for blade in blades:
            assert isinstance(blade, trimesh.Trimesh)

    def test_blades_have_faces(self):
        fan = _make_simple_fan(blade_count=4)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        for blade in blades:
            assert len(blade.faces) > 0

    def test_no_nan_vertices(self):
        fan = _make_simple_fan(blade_count=5)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        for blade in blades:
            assert not np.any(np.isnan(blade.vertices)), "NaN vertices found"

    def test_each_blade_is_3d_printable_solid(self):
        fan = _make_simple_fan(blade_count=5)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        for blade in blades:
            assert is_3d_printable_mesh(blade)

    def test_blades_rotated_correctly(self):
        """Blades should be evenly distributed around the axis."""
        import math
        fan = _make_simple_fan(blade_count=4)
        stage = fan.stages[0]
        blades = generate_stage_geometry(stage, fan)
        # Centroid of blade 0 and blade 1 should be 90° apart
        c0 = blades[0].centroid[:2]  # XY components
        c1 = blades[1].centroid[:2]
        angle_0 = math.atan2(c0[1], c0[0])
        angle_1 = math.atan2(c1[1], c1[0])
        angle_diff = abs(angle_1 - angle_0)
        expected_diff = 2 * math.pi / 4  # 90°
        # Allow some tolerance
        assert abs(angle_diff - expected_diff) < 0.1 or abs(angle_diff - (2 * math.pi - expected_diff)) < 0.1


# ---------------------------------------------------------------------------
# Hub geometry
# ---------------------------------------------------------------------------


class TestHubGeometry:
    def test_hub_generated(self):
        fan = _make_simple_fan()
        hub = generate_hub(fan)
        assert isinstance(hub, trimesh.Trimesh)
        assert len(hub.vertices) > 0

    def test_hub_radius(self):
        fan = _make_simple_fan()
        hub = generate_hub(fan)
        # Hub centroid should be near origin XY
        c = hub.centroid
        assert abs(c[0]) < 1e-6
        assert abs(c[1]) < 1e-6

    def test_ducted_hub_stays_inside_duct_length(self):
        fan = _make_simple_fan()
        fan.duct = DuctConfig(
            enabled=True,
            inner_diameter_m=0.122,
            wall_thickness_m=0.003,
            total_length_m=0.080,
            inlet_clearance_m=0.010,
            outlet_clearance_m=0.010,
        )
        hub = generate_hub(fan)
        z_min, z_max = hub.bounds[:, 2]
        assert z_min == pytest.approx(0.0)
        assert z_max == pytest.approx(0.080)


class TestDuctGeometry:
    def test_duct_is_hollow_annulus(self):
        fan = FanConfig(
            name="ducted",
            max_diameter_m=0.12,
            hub_diameter_m=0.03,
            rpm=5000.0,
            duct=DuctConfig(
                enabled=True,
                inner_diameter_m=0.122,
                wall_thickness_m=0.003,
                total_length_m=0.08,
                inlet_clearance_m=0.01,
                outlet_clearance_m=0.01,
            ),
            stages=[
                StageConfig(
                    name="rotor_1",
                    type=StageType.ROTOR,
                    axial_position_m=0.02,
                    blade_count=5,
                    rpm=5000.0,
                    blade=BladeConfig(),
                )
            ],
        )
        duct = generate_duct(fan)
        radii = np.linalg.norm(duct.vertices[:, :2], axis=1)
        assert radii.min() == pytest.approx(0.061)
        assert radii.max() == pytest.approx(0.064)


# ---------------------------------------------------------------------------
# Full assembly
# ---------------------------------------------------------------------------


class TestFullAssembly:
    def test_assembly_has_hub(self):
        fan = _make_simple_fan()
        meshes = generate_full_assembly(fan, fan.stages)
        assert "hub" in meshes

    def test_assembly_has_rotor_key(self):
        fan = _make_simple_fan()
        meshes = generate_full_assembly(fan, fan.stages)
        assert "rotor_1" in meshes

    def test_assembly_has_full_assembly(self):
        fan = _make_simple_fan()
        meshes = generate_full_assembly(fan, fan.stages)
        assert "full_assembly" in meshes

    def test_full_assembly_does_not_duplicate_aggregate_meshes(self):
        fan = _make_simple_fan()
        meshes = generate_full_assembly(fan, fan.stages)
        expected_faces = len(meshes["rotor_1"].faces) + len(meshes["hub"].faces)
        assert len(meshes["full_assembly"].faces) == expected_faces

    def test_generated_meshes_are_3d_printable_solids(self):
        fan = _make_simple_fan()
        meshes = generate_full_assembly(fan, fan.stages)
        for name, mesh in meshes.items():
            assert is_3d_printable_mesh(mesh), f"Mesh is not printable: {name}"

    def test_build_geometry_resolves_inherited_profiles(self):
        base_blade = BladeConfig(
            chord_profile=Profile.constant(0.025),
            twist_profile_deg=Profile.constant(30.0),
        )
        inherited_blade = BladeConfig(
            chord_profile=Profile(
                type=ProfileType.INHERIT,
                from_stage="rotor_1",
                scale=0.9,
            ),
            twist_profile_deg=Profile.constant(25.0),
        )
        fan = FanConfig(
            name="inherited_geometry",
            max_diameter_m=0.12,
            hub_diameter_m=0.03,
            rpm=5000.0,
            stages=[
                StageConfig(
                    name="rotor_1",
                    type=StageType.ROTOR,
                    axial_position_m=0.0,
                    blade_count=3,
                    blade=base_blade,
                ),
                StageConfig(
                    name="rotor_2",
                    type=StageType.ROTOR,
                    axial_position_m=0.04,
                    blade_count=3,
                    blade=inherited_blade,
                ),
            ],
        )
        meshes = build_geometry(FanCFDConfig(fan=fan))
        assert "rotor_2" in meshes
        for name, mesh in meshes.items():
            assert is_3d_printable_mesh(mesh), f"Mesh is not printable: {name}"

    def test_multistage_assembly_keys(self):
        fan = _make_simple_fan(n_stages=4)
        meshes = generate_full_assembly(fan, fan.stages)
        assert "rotor_1" in meshes
        assert "stator_2" in meshes

    def test_custom_stage_names_are_used_as_sanitized_mesh_keys(self):
        fan = _make_simple_fan(n_stages=2)
        fan.stages[0].name = "front rotor"
        fan.stages[1].name = "exit-stator"

        meshes = generate_full_assembly(fan, fan.stages)

        assert "front_rotor" in meshes
        assert "exit_stator" in meshes

    def test_duct_present_when_configured(self):
        fan = FanConfig(
            name="ducted",
            max_diameter_m=0.12,
            hub_diameter_m=0.03,
            rpm=5000.0,
            duct=DuctConfig(
                enabled=True,
                inner_diameter_m=0.122,
                wall_thickness_m=0.003,
                total_length_m=0.08,
                inlet_clearance_m=0.01,
                outlet_clearance_m=0.01,
            ),
            stages=[
                StageConfig(
                    name="rotor_1",
                    type=StageType.ROTOR,
                    axial_position_m=0.02,
                    blade_count=5,
                    rpm=5000.0,
                    blade=BladeConfig(
                        chord_profile=Profile.constant(0.025),
                        twist_profile_deg=Profile.constant(30.0),
                    ),
                )
            ],
        )
        meshes = generate_full_assembly(fan, fan.stages)
        assert "duct" in meshes


# ---------------------------------------------------------------------------
# STL export and validation
# ---------------------------------------------------------------------------


class TestSTLExport:
    def test_stl_files_created(self):
        fan = _make_simple_fan(blade_count=3)
        meshes = generate_full_assembly(fan, fan.stages)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_stl_files(meshes, Path(tmpdir))
            assert len(paths) > 0
            for name, path in paths.items():
                assert path.exists(), f"STL file missing: {path}"

    def test_stl_files_non_empty(self):
        fan = _make_simple_fan(blade_count=3)
        meshes = generate_full_assembly(fan, fan.stages)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_stl_files(meshes, Path(tmpdir))
            for name, path in paths.items():
                assert path.stat().st_size > 0, f"STL file is empty: {path}"

    def test_validation_passes_for_valid_stl(self):
        fan = _make_simple_fan(blade_count=3)
        meshes = generate_full_assembly(fan, fan.stages)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_stl_files(meshes, Path(tmpdir))
            results = validate_stl_files(paths)
            for name, ok in results.items():
                assert ok, f"Validation failed for '{name}'"

    def test_validation_fails_for_missing_file(self):
        paths = {"missing": Path("/nonexistent/file.stl")}
        results = validate_stl_files(paths)
        assert results["missing"] is False

    def test_validation_fails_for_open_surface_stl(self):
        mesh = trimesh.Trimesh(
            vertices=np.array(
                [
                    [0.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                ]
            ),
            faces=np.array([[0, 1, 2]]),
            process=False,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "open_surface.stl"
            mesh.export(path)
            results = validate_stl_files({"open_surface": path})
            assert results["open_surface"] is False

    def test_export_rejects_open_surface_mesh(self):
        mesh = trimesh.Trimesh(
            vertices=np.array(
                [
                    [0.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                ]
            ),
            faces=np.array([[0, 1, 2]]),
            process=False,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="not 3D-printable"):
                export_stl_files({"open_surface": mesh}, Path(tmpdir))

    def test_4_stage_generates_4_stl_files(self):
        """4-stage config should generate at least 4 per-stage STL files."""
        fan = _make_simple_fan(blade_count=4, n_stages=4)
        meshes = generate_full_assembly(fan, fan.stages)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_stl_files(meshes, Path(tmpdir))
            per_stage_keys = [k for k in paths if k.startswith(("rotor_", "stator_"))]
            assert len(per_stage_keys) >= 4
