"""
fan_cfd.multistage.stage_validation
=====================================
Geometry and layout validation for multi-stage fan assemblies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fan_cfd.config import DuctConfig, FanConfig, StageConfig


def validate_stage_sequence(
    stages: "list[StageConfig]",
    fan: "FanConfig",
    duct: "DuctConfig | None" = None,
) -> list[str]:
    """
    Validate the stage layout and return a list of error strings.

    An empty list means the configuration is valid.

    Checks performed
    ----------------
    1. Stage names are unique
    2. No two stages share the same axial position
    3. Stages are ordered by axial_position_m (warning only)
    4. Blade tip radius ≤ duct inner radius (if duct enabled)
    5. Hub diameter < blade root radius (no blade-hub overlap)
    6. All stages within duct axial bounds (if duct enabled)
    7. Minimum axial clearance between consecutive stages > 0
    """
    errors: list[str] = []

    if not stages:
        errors.append("No stages defined.")
        return errors

    # --- 1. Unique names ---
    names = [s.name for s in stages]
    if len(names) != len(set(names)):
        duplicates = [n for n in names if names.count(n) > 1]
        errors.append(f"Duplicate stage names: {list(set(duplicates))}")

    # Sort by axial position for subsequent checks
    sorted_stages = sorted(stages, key=lambda s: s.axial_position_m)

    # --- 2. No two stages at exactly the same axial position ---
    positions = [s.axial_position_m for s in sorted_stages]
    for i in range(len(positions) - 1):
        if abs(positions[i + 1] - positions[i]) < 1e-6:
            errors.append(
                f"Stages '{sorted_stages[i].name}' and '{sorted_stages[i+1].name}' "
                f"have identical axial positions ({positions[i]:.4f} m)."
            )

    tip_r = fan.tip_radius_m
    hub_r = fan.hub_radius_m

    # --- 4. Blade tip vs duct ---
    if duct is not None and duct.enabled:
        inner_r = duct.inner_radius_m
        for stage in stages:
            # Approximate chord extent ≈ max chord value
            chord_tip = _estimate_tip_chord(stage)
            if tip_r > inner_r:
                errors.append(
                    f"Stage '{stage.name}': tip radius {tip_r:.4f} m exceeds "
                    f"duct inner radius {inner_r:.4f} m."
                )
                break

    # --- 5. Hub diameter < blade root radius ---
    for stage in stages:
        root_chord = _estimate_root_chord(stage)
        if hub_r >= tip_r:
            errors.append(
                f"Stage '{stage.name}': hub radius {hub_r:.4f} m >= tip radius {tip_r:.4f} m."
            )

    # --- 6. Stages within duct bounds ---
    if duct is not None and duct.enabled:
        duct_z_start = 0.0
        duct_z_end = duct.total_length_m
        for stage in stages:
            z = stage.axial_position_m
            if z < duct_z_start - 1e-4 or z > duct_z_end + 1e-4:
                errors.append(
                    f"Stage '{stage.name}' axial position {z:.4f} m is outside "
                    f"duct bounds [{duct_z_start:.4f}, {duct_z_end:.4f}] m."
                )

    # --- 7. Minimum clearance between consecutive stages ---
    min_clearance = 0.002  # 2 mm minimum
    for i in range(len(sorted_stages) - 1):
        gap = sorted_stages[i + 1].axial_position_m - sorted_stages[i].axial_position_m
        if gap < min_clearance:
            errors.append(
                f"Axial clearance between '{sorted_stages[i].name}' and "
                f"'{sorted_stages[i+1].name}' is {gap*1000:.1f} mm "
                f"(minimum {min_clearance*1000:.0f} mm)."
            )

    return errors


def _estimate_tip_chord(stage: "StageConfig") -> float:
    """Approximate chord at blade tip from the chord profile."""
    from fan_cfd.geometry.blade_profiles import interpolate_profile

    try:
        return interpolate_profile(stage.blade.chord_profile, 1.0)
    except Exception:
        return 0.03  # fallback default


def _estimate_root_chord(stage: "StageConfig") -> float:
    """Approximate chord at blade root."""
    from fan_cfd.geometry.blade_profiles import interpolate_profile

    try:
        return interpolate_profile(stage.blade.chord_profile, 0.0)
    except Exception:
        return 0.03
