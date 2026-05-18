"""
tests/test_profile_inheritance.py
=================================
Regression tests for recursive inherited-profile resolution.
"""

import pytest

from fan_cfd.config import BladeConfig, Profile, ProfileType, StageConfig, StageType
from fan_cfd.multistage.stage_config import resolve_inherited_profiles


def _make_rotor(name: str, chord_profile: Profile) -> StageConfig:
    return StageConfig(
        name=name,
        type=StageType.ROTOR,
        axial_position_m=0.0,
        blade_count=5,
        rpm=5000.0,
        blade=BladeConfig(
            chord_profile=chord_profile,
            twist_profile_deg=Profile.constant(30.0),
        ),
    )


def test_recursive_inherit_chain_resolves_and_combines_scales():
    rotor_1 = _make_rotor("rotor_1", Profile.constant(0.030))
    rotor_2 = _make_rotor(
        "rotor_2",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_1",
            scale=0.8,
        ),
    )
    rotor_3 = _make_rotor(
        "rotor_3",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_2",
            scale=0.5,
        ),
    )

    resolved = resolve_inherited_profiles([rotor_1, rotor_2, rotor_3])

    assert resolved[0].blade.chord_profile.type == ProfileType.CONSTANT
    assert resolved[0].blade.chord_profile.value == pytest.approx(0.030)
    assert resolved[1].blade.chord_profile.type == ProfileType.CONSTANT
    assert resolved[1].blade.chord_profile.value == pytest.approx(0.024)
    assert resolved[2].blade.chord_profile.type == ProfileType.CONSTANT
    assert resolved[2].blade.chord_profile.value == pytest.approx(0.012)


def test_recursive_inherit_with_scale_one_still_resolves_source_profile():
    rotor_1 = _make_rotor("rotor_1", Profile.constant(0.025))
    rotor_2 = _make_rotor(
        "rotor_2",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_1",
            scale=1.0,
        ),
    )
    rotor_3 = _make_rotor(
        "rotor_3",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_2",
            scale=1.0,
        ),
    )

    resolved = resolve_inherited_profiles([rotor_1, rotor_2, rotor_3])

    assert resolved[2].blade.chord_profile.type == ProfileType.CONSTANT
    assert resolved[2].blade.chord_profile.value == pytest.approx(0.025)


def test_circular_profile_inheritance_raises_runtime_error():
    rotor_1 = _make_rotor(
        "rotor_1",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_2",
            scale=1.0,
        ),
    )
    rotor_2 = _make_rotor(
        "rotor_2",
        Profile(
            type=ProfileType.INHERIT,
            from_stage="rotor_1",
            scale=1.0,
        ),
    )

    with pytest.raises(RuntimeError, match="Circular profile inheritance"):
        resolve_inherited_profiles([rotor_1, rotor_2])


def test_apply_profile_scale_rejects_unresolved_inherit_profile():
    from fan_cfd.geometry.blade_profiles import apply_profile_scale

    profile = Profile(
        type=ProfileType.INHERIT,
        from_stage="rotor_1",
        scale=1.0,
    )

    with pytest.raises(RuntimeError, match="unresolved INHERIT"):
        apply_profile_scale(profile, 0.5)
