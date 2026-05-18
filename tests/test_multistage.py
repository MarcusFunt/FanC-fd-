"""
tests/test_multistage.py
=========================
Tests for multi-stage assembly mode, stage validation, and profile inheritance.
"""

import tempfile
from pathlib import Path

import pytest

from fan_cfd.config import (
    BladeConfig,
    DuctConfig,
    FanConfig,
    Profile,
    ProfileType,
    StageConfig,
    StageType,
)
from fan_cfd.geometry.assembly_geometry import generate_full_assembly
from fan_cfd.geometry.cad_export import export_stl_files
from fan_cfd.multistage.stage_config import (
    AssemblyMode,
    detect_assembly_mode,
    resolve_inherited_profiles,
)
from fan_cfd.multistage.stage_spacing import (
    auto_space_stages,
    compute_axial_clearances,
    suggest_stage_positions,
)
from fan_cfd.multistage.stage_validation import validate_stage_sequence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rotor(name, axial_pos, blade_count=5, rpm=5000.0):
    return StageConfig(
        name=name,
        type=StageType.ROTOR,
        axial_position_m=axial_pos,
        blade_count=blade_count,
        rpm=rpm,
        blade=BladeConfig(
            chord_profile=Profile.constant(0.025),
            twist_profile_deg=Profile.constant(30.0),
        ),
    )


def _make_stator(name, axial_pos, blade_count=7):
    return StageConfig(
        name=name,
        type=StageType.STATOR,
        axial_position_m=axial_pos,
        blade_count=blade_count,
        blade=BladeConfig(
            chord_profile=Profile.constant(0.025),
            twist_profile_deg=Profile.constant(-20.0),
        ),
    )


def _make_fan(stages, max_d=0.12, hub_d=0.03, duct=None):
    return FanConfig(
        name="test",
        max_diameter_m=max_d,
        hub_diameter_m=hub_d,
        rpm=5000.0,
        duct=duct,
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Assembly mode detection
# ---------------------------------------------------------------------------


class TestAssemblyMode:
    def test_single_rotor(self):
        stages = [_make_rotor("rotor_1", 0.0)]
        mode = detect_assembly_mode(stages)
        assert mode == AssemblyMode.SINGLE_STAGE

    def test_rotor_stator(self):
        stages = [_make_rotor("rotor_1", 0.0), _make_stator("stator_1", 0.04)]
        mode = detect_assembly_mode(stages)
        assert mode == AssemblyMode.ROTOR_STATOR

    def test_multi_stage_axial(self):
        stages = [
            _make_rotor("rotor_1", 0.0),
            _make_stator("stator_1", 0.04),
            _make_rotor("rotor_2", 0.08),
            _make_stator("stator_2", 0.12),
        ]
        mode = detect_assembly_mode(stages)
        assert mode == AssemblyMode.MULTI_STAGE_AXIAL

    def test_turbomolecular_style(self):
        # 6 stages with very tight spacing
        stages = []
        for i in range(6):
            stype = StageType.ROTOR if i % 2 == 0 else StageType.STATOR
            name = f"{'rotor' if stype == StageType.ROTOR else 'stator'}_{i//2+1}"
            s = StageConfig(
                name=name,
                type=stype,
                axial_position_m=i * 0.008,  # 8 mm spacing = very tight
                blade_count=20,
                rpm=30000.0 if stype == StageType.ROTOR else None,
                blade=BladeConfig(
                    chord_profile=Profile.constant(0.010),
                    twist_profile_deg=Profile.constant(55.0),
                ),
            )
            stages.append(s)
        mode = detect_assembly_mode(stages)
        assert mode == AssemblyMode.TURBOMOLECULAR_STYLE


# ---------------------------------------------------------------------------
# Stage validation
# ---------------------------------------------------------------------------


class TestStageValidation:
    def test_valid_config_no_errors(self):
        stages = [_make_rotor("rotor_1", 0.0)]
        fan = _make_fan(stages)
        errors = validate_stage_sequence(stages, fan)
        assert errors == []

    def test_duplicate_names_detected(self):
        stages = [
            _make_rotor("rotor_1", 0.0),
            _make_rotor("rotor_1", 0.05),  # duplicate name!
        ]
        fan = _make_fan(stages)
        errors = validate_stage_sequence(stages, fan)
        assert any("Duplicate" in e for e in errors)

    def test_overlapping_axial_positions_detected(self):
        stages = [
            _make_rotor("rotor_1", 0.0),
            _make_rotor("rotor_2", 0.0),  # same position
        ]
        fan = _make_fan(stages)
        errors = validate_stage_sequence(stages, fan)
        assert any("identical axial positions" in e for e in errors)

    def test_tip_duct_interference_detected(self):
        stages = [_make_rotor("rotor_1", 0.01)]
        duct = DuctConfig(
            enabled=True,
            inner_diameter_m=0.100,  # too small! tip is at 0.06
            wall_thickness_m=0.003,
            total_length_m=0.08,
            inlet_clearance_m=0.01,
            outlet_clearance_m=0.01,
        )
        fan = _make_fan(stages, max_d=0.12, duct=duct)
        errors = validate_stage_sequence(stages, fan, duct)
        assert any("tip radius" in e for e in errors)

    def test_stage_outside_duct_detected(self):
        stages = [
            _make_rotor("rotor_1", 0.005),
            _make_rotor("rotor_2", 0.20),  # outside duct!
        ]
        duct = DuctConfig(
            enabled=True,
            inner_diameter_m=0.122,
            wall_thickness_m=0.003,
            total_length_m=0.08,  # duct ends at 0.08 m
            inlet_clearance_m=0.01,
            outlet_clearance_m=0.01,
        )
        fan = _make_fan(stages, duct=duct)
        errors = validate_stage_sequence(stages, fan, duct)
        assert any("outside duct" in e for e in errors)

    def test_minimum_clearance_violation(self):
        stages = [
            _make_rotor("rotor_1", 0.0),
            _make_stator("stator_1", 0.001),  # only 1 mm gap — below 2 mm minimum
        ]
        fan = _make_fan(stages)
        errors = validate_stage_sequence(stages, fan)
        assert any("clearance" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Inherited profiles
# ---------------------------------------------------------------------------


class TestInheritedProfiles:
    def test_resolved_profiles_no_inherit(self):
        stages = [
            _make_rotor("rotor_1", 0.0),
            _make_rotor("rotor_2", 0.05),
        ]
        resolved = resolve_inherited_profiles(stages)
        for s in resolved:
            assert s.blade.chord_profile.type != ProfileType.INHERIT

    def test_inherit_resolves_correctly(self):
        rotor_1 = _make_rotor("rotor_1", 0.0)
        rotor_1 = StageConfig(
            name="rotor_1",
            type=StageType.ROTOR,
            axial_position_m=0.0,
            blade_count=5,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile.constant(0.030),
                twist_profile_deg=Profile.constant(35.0),
            ),
        )

        rotor_2 = StageConfig(
            name="rotor_2",
            type=StageType.ROTOR,
            axial_position_m=0.05,
            blade_count=5,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile(
                    type=ProfileType.INHERIT,
                    from_stage="rotor_1",
                    scale=0.9,
                ),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )

        resolved = resolve_inherited_profiles([rotor_1, rotor_2])
        r2 = resolved[1]
        # Chord should be resolved to CONSTANT with value = 0.030 * 0.9 = 0.027
        assert r2.blade.chord_profile.type == ProfileType.CONSTANT
        assert r2.blade.chord_profile.value == pytest.approx(0.027)

    def test_inherit_with_scale_1_gives_same_value(self):
        rotor_1 = StageConfig(
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
        rotor_2 = StageConfig(
            name="rotor_2",
            type=StageType.ROTOR,
            axial_position_m=0.05,
            blade_count=5,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile(
                    type=ProfileType.INHERIT,
                    from_stage="rotor_1",
                    scale=1.0,
                ),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )
        resolved = resolve_inherited_profiles([rotor_1, rotor_2])
        assert resolved[1].blade.chord_profile.value == pytest.approx(0.025)

    def test_inherit_missing_stage_raises(self):
        rotor = StageConfig(
            name="rotor_2",
            type=StageType.ROTOR,
            axial_position_m=0.0,
            blade_count=5,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile(
                    type=ProfileType.INHERIT,
                    from_stage="nonexistent_stage",
                    scale=1.0,
                ),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )
        with pytest.raises(ValueError, match="nonexistent_stage"):
            resolve_inherited_profiles([rotor])


# ---------------------------------------------------------------------------
# Stage spacing
# ---------------------------------------------------------------------------


class TestStageSpacing:
    def test_compute_clearances(self):
        stages = [
            _make_rotor("r1", 0.0),
            _make_stator("s1", 0.04),
            _make_rotor("r2", 0.09),
        ]
        gaps = compute_axial_clearances(stages)
        assert len(gaps) == 2
        assert gaps[0] == pytest.approx(0.04)
        assert gaps[1] == pytest.approx(0.05)

    def test_suggest_positions_count(self):
        fan = _make_fan([_make_rotor("r1", 0.0)])
        positions = suggest_stage_positions(fan, 4, spacing_m=0.04)
        assert len(positions) == 4

    def test_suggest_positions_evenly_spaced(self):
        fan = _make_fan([_make_rotor("r1", 0.0)])
        positions = suggest_stage_positions(fan, 4, spacing_m=0.05, start_offset_m=0.01)
        for i in range(len(positions) - 1):
            assert positions[i + 1] - positions[i] == pytest.approx(0.05)

    def test_auto_space_stages(self):
        stages = [_make_rotor("r1", 0.0), _make_stator("s1", 0.0), _make_rotor("r2", 0.0)]
        positions = auto_space_stages(stages, total_length_m=0.1, margin_m=0.01)
        assert len(positions) == 3
        assert positions[0] == pytest.approx(0.01)
        assert positions[-1] == pytest.approx(0.09)


# ---------------------------------------------------------------------------
# 4-stage geometry generation
# ---------------------------------------------------------------------------


class TestFourStageGeometry:
    def test_4_stage_generates_4_stl_files(self):
        stages = [
            _make_rotor("rotor_1", 0.01, blade_count=3),
            _make_stator("stator_1", 0.04, blade_count=4),
            _make_rotor("rotor_2", 0.07, blade_count=3),
            _make_stator("stator_2", 0.10, blade_count=4),
        ]
        fan = _make_fan(stages)
        meshes = generate_full_assembly(fan, stages)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_stl_files(meshes, Path(tmpdir))
            per_stage = [k for k in paths if k.startswith(("rotor_", "stator_"))]
            assert len(per_stage) == 4
