"""
tests/test_config.py
====================
Tests for fan_cfd.config — Pydantic models, backward compat, and validation.
"""

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from fan_cfd.config import (
    BladeConfig,
    FanCFDConfig,
    FanConfig,
    Profile,
    ProfileType,
    StageConfig,
    StageType,
    _convert_legacy_config,
    load_config,
)

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------


class TestProfile:
    def test_constant_profile(self):
        p = Profile.constant(30.0)
        assert p.type == ProfileType.CONSTANT
        assert p.value == 30.0

    def test_linear_profile(self):
        p = Profile.linear(40.0, 20.0)
        assert p.type == ProfileType.LINEAR
        assert len(p.points) == 2
        assert p.points[0] == (0.0, 40.0)
        assert p.points[1] == (1.0, 20.0)

    def test_control_points_profile(self):
        pts = [(0.0, 0.03), (0.5, 0.025), (1.0, 0.02)]
        p = Profile.control_points(pts)
        assert p.type == ProfileType.CONTROL_POINTS
        assert len(p.points) == 3

    def test_control_points_requires_at_least_2(self):
        with pytest.raises(ValidationError):
            Profile(type=ProfileType.CONTROL_POINTS, points=[(0.0, 1.0)])

    def test_constant_requires_value(self):
        with pytest.raises(ValidationError):
            Profile(type=ProfileType.CONSTANT)

    def test_inherit_requires_from_stage(self):
        with pytest.raises(ValidationError):
            Profile(type=ProfileType.INHERIT)

    def test_inherit_profile_valid(self):
        p = Profile(type=ProfileType.INHERIT, from_stage="rotor_1", scale=0.9)
        assert p.from_stage == "rotor_1"
        assert p.scale == 0.9


# ---------------------------------------------------------------------------
# FanConfig validation
# ---------------------------------------------------------------------------


class TestFanConfig:
    def _make_stage(self, name="rotor_1", type_=StageType.ROTOR, axial=0.0, blade_count=5):
        return StageConfig(
            name=name,
            type=type_,
            axial_position_m=axial,
            blade_count=blade_count,
            rpm=5000.0,
            blade=BladeConfig(
                chord_profile=Profile.constant(0.03),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )

    def test_hub_must_be_smaller_than_tip(self):
        with pytest.raises(ValidationError):
            FanConfig(
                name="test",
                max_diameter_m=0.10,
                hub_diameter_m=0.12,  # larger than max!
                rpm=5000.0,
                stages=[self._make_stage()],
            )

    def test_rpm_propagated_to_rotor_stages(self):
        stage = StageConfig(
            name="rotor_1",
            type=StageType.ROTOR,
            axial_position_m=0.0,
            blade_count=5,
            # No rpm set — should inherit from fan
            blade=BladeConfig(
                chord_profile=Profile.constant(0.03),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )
        fan = FanConfig(
            name="test",
            max_diameter_m=0.12,
            hub_diameter_m=0.03,
            rpm=5000.0,
            stages=[stage],
        )
        assert fan.stages[0].rpm == 5000.0

    def test_omega_rad_s(self):
        stage_with_fan = StageConfig(
            name="rotor_1",
            type=StageType.ROTOR,
            axial_position_m=0.0,
            blade_count=5,
            rpm=6000.0,
            blade=BladeConfig(
                chord_profile=Profile.constant(0.03),
                twist_profile_deg=Profile.constant(30.0),
            ),
        )
        expected_omega = 6000.0 * 2.0 * math.pi / 60.0
        assert abs(stage_with_fan.omega_rad_s - expected_omega) < 1e-6

    def test_rotor_stages_filter(self):
        fan = FanConfig(
            name="test",
            max_diameter_m=0.12,
            hub_diameter_m=0.03,
            rpm=5000.0,
            stages=[
                self._make_stage("rotor_1", StageType.ROTOR),
                self._make_stage("stator_1", StageType.STATOR),
            ],
        )
        assert len(fan.rotor_stages) == 1
        assert len(fan.stator_stages) == 1


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_convert_legacy_single_blade(self):
        raw = {
            "fan": {
                "name": "legacy_fan",
                "max_diameter_m": 0.12,
                "hub_diameter_m": 0.03,
                "rpm": 5000.0,
                "blade_count": 5,
                "blade": {
                    "airfoil": "naca4412",
                    "chord_profile": {"type": "constant", "value": 0.03},
                    "twist_profile_deg": {"type": "constant", "value": 30.0},
                },
            },
            "cfd": {},
        }
        converted = _convert_legacy_config(raw)
        assert "stages" in converted["fan"]
        assert len(converted["fan"]["stages"]) == 1
        assert converted["fan"]["stages"][0]["type"] == "rotor"

    def test_convert_legacy_rotor_stator(self):
        raw = {
            "fan": {
                "name": "legacy_rs",
                "max_diameter_m": 0.12,
                "hub_diameter_m": 0.03,
                "rpm": 5000.0,
                "blade_count": 5,
                "blade": {
                    "airfoil": "naca4412",
                    "chord_profile": {"type": "constant", "value": 0.03},
                    "twist_profile_deg": {"type": "constant", "value": 30.0},
                },
                "rotor_stator": {
                    "stator_blade_count": 7,
                    "stator_axial_position_m": 0.04,
                },
            },
        }
        converted = _convert_legacy_config(raw)
        stages = converted["fan"]["stages"]
        assert len(stages) == 2
        assert stages[0]["type"] == "rotor"
        assert stages[1]["type"] == "stator"
        assert stages[1]["blade_count"] == 7

    def test_canonical_config_unchanged(self):
        """Configs already using 'stages' are passed through unchanged."""
        raw = {
            "fan": {
                "name": "modern",
                "max_diameter_m": 0.12,
                "hub_diameter_m": 0.03,
                "rpm": 5000.0,
                "stages": [
                    {
                        "name": "rotor_1",
                        "type": "rotor",
                        "axial_position_m": 0.0,
                        "blade_count": 5,
                        "blade": {
                            "chord_profile": {"type": "constant", "value": 0.03},
                            "twist_profile_deg": {"type": "constant", "value": 30.0},
                        },
                    }
                ],
            }
        }
        converted = _convert_legacy_config(raw)
        assert converted["fan"]["stages"] == raw["fan"]["stages"]


# ---------------------------------------------------------------------------
# Load from YAML files
# ---------------------------------------------------------------------------


class TestLoadConfig:
    @pytest.mark.parametrize(
        "filename",
        [
            "example_single_stage_rotor.yaml",
            "example_ducted_rotor.yaml",
            "example_rotor_stator.yaml",
            "example_multistage_axial.yaml",
            "example_turbomolecular_style.yaml",
            "jetengine_inspired_axial_compressor.yaml",
            "openfoam_smoke_test.yaml",
        ],
    )
    def test_load_example_config(self, filename):
        path = CONFIGS_DIR / filename
        if not path.exists():
            pytest.skip(f"Config not found: {path}")
        config = load_config(path)
        assert isinstance(config, FanCFDConfig)
        assert config.fan.name
        assert len(config.fan.stages) >= 1

    def test_single_stage_rotor_details(self):
        path = CONFIGS_DIR / "example_single_stage_rotor.yaml"
        if not path.exists():
            pytest.skip("Config not found")
        config = load_config(path)
        assert config.fan.max_diameter_m == pytest.approx(0.120)
        assert config.fan.rpm == 5000.0
        assert len(config.fan.stages) == 1
        assert config.fan.stages[0].type == StageType.ROTOR
        assert config.fan.stages[0].blade_count == 5

    def test_multistage_has_inherit(self):
        path = CONFIGS_DIR / "example_multistage_axial.yaml"
        if not path.exists():
            pytest.skip("Config not found")
        config = load_config(path)
        # rotor_2 should have INHERIT chord_profile
        rotor_2 = next(s for s in config.fan.stages if s.name == "rotor_2")
        assert rotor_2.blade.chord_profile.type == ProfileType.INHERIT
        assert rotor_2.blade.chord_profile.from_stage == "rotor_1"
        assert rotor_2.blade.chord_profile.scale == pytest.approx(0.9)

    def test_jetengine_inspired_preset_details(self):
        path = CONFIGS_DIR / "jetengine_inspired_axial_compressor.yaml"
        if not path.exists():
            pytest.skip("Config not found")
        config = load_config(path)
        rotor_stages = config.fan.rotor_stages
        stator_stages = config.fan.stator_stages
        assert config.fan.rpm == pytest.approx(15000.0)
        assert config.cfd.inlet.velocity_m_s == pytest.approx(70.0)
        assert len(config.fan.stages) == 12
        assert len(rotor_stages) == 6
        assert len(stator_stages) == 6
        assert [stage.blade_count for stage in rotor_stages] == [24, 25, 25, 26, 27, 28]

    def test_config_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")
