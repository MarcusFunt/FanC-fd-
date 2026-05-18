"""
fan_cfd.multistage.stage_config
================================
Assembly mode detection and inherited-profile resolution for multi-stage fans.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from fan_cfd.geometry.blade_profiles import apply_profile_scale
from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import Profile, StageConfig

logger = get_logger(__name__)


class AssemblyMode(str, Enum):
    SINGLE_STAGE = "single_stage"
    ROTOR_STATOR = "rotor_stator"
    MULTI_STAGE_AXIAL = "multi_stage_axial"
    TURBOMOLECULAR_STYLE = "turbomolecular_style"


def detect_assembly_mode(stages: "list[StageConfig]") -> AssemblyMode:
    """
    Classify the assembly based on its stage sequence.

    Rules
    -----
    1 stage, rotor only           → SINGLE_STAGE
    2 stages, one rotor+stator    → ROTOR_STATOR
    ≥4 stages alternating R/S     → MULTI_STAGE_AXIAL
    ≥6 stages, tight spacing      → TURBOMOLECULAR_STYLE (heuristic)
    Anything else                  → MULTI_STAGE_AXIAL
    """
    from fan_cfd.config import StageType

    n = len(stages)
    n_rotor = sum(1 for s in stages if s.type == StageType.ROTOR)
    n_stator = sum(1 for s in stages if s.type == StageType.STATOR)

    if n == 1:
        return AssemblyMode.SINGLE_STAGE

    if n == 2 and n_rotor == 1 and n_stator == 1:
        return AssemblyMode.ROTOR_STATOR

    # Turbomolecular heuristic: many stages, small axial spacing
    if n >= 6 and n_rotor >= 3 and n_stator >= 3:
        if n >= 2:
            positions = sorted(s.axial_position_m for s in stages)
            avg_spacing = (positions[-1] - positions[0]) / (n - 1) if n > 1 else 0.0
            if avg_spacing < 0.015:  # very tight stages
                return AssemblyMode.TURBOMOLECULAR_STYLE

    return AssemblyMode.MULTI_STAGE_AXIAL


def resolve_inherited_profiles(stages: "list[StageConfig]") -> "list[StageConfig]":
    """
    Walk through all stages and resolve any INHERIT-type profiles.

    For each stage, if chord_profile or twist_profile_deg is of type INHERIT,
    look up the referenced stage's profile and create a scaled copy.

    Returns a new list of stages with all profiles fully resolved (no INHERIT).
    """
    from fan_cfd.config import ProfileType, StageConfig

    stage_map = {s.name: s for s in stages}
    resolved_stages: list[StageConfig] = []

    for stage in stages:
        blade = stage.blade
        chord_p = blade.chord_profile
        twist_p = blade.twist_profile_deg
        rake_p = blade.rake_profile
        skew_p = blade.skew_profile

        # Resolve chord
        chord_p = _resolve_one(chord_p, "chord_profile", stage, stage_map)
        # Resolve twist
        twist_p = _resolve_one(twist_p, "twist_profile_deg", stage, stage_map)
        # Resolve rake
        if rake_p is not None:
            rake_p = _resolve_one(rake_p, "rake_profile", stage, stage_map)
        # Resolve skew
        if skew_p is not None:
            skew_p = _resolve_one(skew_p, "skew_profile", stage, stage_map)

        # Rebuild blade config with resolved profiles
        from fan_cfd.config import BladeConfig

        new_blade = BladeConfig(
            airfoil=blade.airfoil,
            radial_sections=blade.radial_sections,
            chord_profile=chord_p,
            twist_profile_deg=twist_p,
            thickness_scale=blade.thickness_scale,
            rake_profile=rake_p,
            skew_profile=skew_p,
        )
        new_stage = StageConfig(
            name=stage.name,
            type=stage.type,
            axial_position_m=stage.axial_position_m,
            blade_count=stage.blade_count,
            blade=new_blade,
            rpm=stage.rpm,
            rotation_direction=stage.rotation_direction,
        )
        resolved_stages.append(new_stage)

    return resolved_stages


def _resolve_one(
    profile: "Profile",
    profile_attr: str,
    stage: "StageConfig",
    stage_map: "dict[str, StageConfig]",
) -> "Profile":
    """Resolve a single profile if it is of type INHERIT."""
    from fan_cfd.config import ProfileType

    if profile.type != ProfileType.INHERIT:
        return profile

    src_name = profile.from_stage
    src_stage = stage_map.get(src_name)
    if src_stage is None:
        raise ValueError(
            f"Stage '{stage.name}' has INHERIT profile '{profile_attr}' "
            f"referencing unknown stage '{src_name}'"
        )

    # Get the source profile attribute
    src_blade = src_stage.blade
    src_profile = getattr(src_blade, profile_attr)

    # Recursively resolve if source is also INHERIT (depth-limited)
    if src_profile.type == ProfileType.INHERIT:
        logger.warning(
            "Stage '%s' inherits from '%s' which also uses INHERIT; "
            "deep inheritance chains are not supported. Using source as-is.",
            stage.name,
            src_name,
        )

    scale = profile.scale
    if abs(scale - 1.0) < 1e-9:
        return src_profile
    return apply_profile_scale(src_profile, scale)
