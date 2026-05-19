"""
fan_cfd.openfoam.cell_zones
============================
Helpers for defining OpenFOAM cell zones used by MRF regions.

In snappyHexMesh, cell zones can be created automatically from STL surfaces
by enabling ``cellZone`` in the geometry/refinementSurfaces section.
This module generates the topoSetDict entries for manual zone creation
as an alternative / fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig, StageConfig
    from fan_cfd.openfoam.mrf_zones import MRFZone


def write_topo_set_dict(zones: "list[MRFZone]", fan: "FanConfig", output_path: Path) -> None:
    """
    Write a ``topoSetDict`` that creates a cylindrical cell zone for each MRF zone.

    The cylinders are sized to contain each rotor stage's swept volume.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tip_r = fan.tip_radius_m

    header = """\
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     |                                                 |
|   \\\\  /    A nd           |                                                 |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

actions
(
"""

    footer = """\
);

// ************************************************************************* //
"""

    action_lines: list[str] = []

    for zone in zones:
        z_min, z_max = _mrf_zone_axial_bounds(zone, fan)
        cell_set = f"{zone.cell_zone}_cells"
        action_lines += [
            "    {",
            f"        name    {cell_set};",
            "        type    cellSet;",
            "        action  new;",
            "        source  cylinderToCell;",
            f"        p1      ({zone.origin[0]} {zone.origin[1]} {z_min});",
            f"        p2      ({zone.origin[0]} {zone.origin[1]} {z_max});",
            f"        radius  {tip_r * 1.05:.6f};",
            "    }",
            "",
            "    {",
            f"        name    {zone.cell_zone};",
            "        type    cellZoneSet;",
            "        action  new;",
            "        source  setToCellZone;",
            f"        set     {cell_set};",
            "    }",
            "",
        ]

    output_path.write_text(header + "\n".join(action_lines) + footer)


def _mrf_zone_axial_bounds(zone: "MRFZone", fan: "FanConfig") -> tuple[float, float]:
    """
    Return compact axial bounds for a rotor MRF cell zone.

    The old fallback zone was a fixed 60 mm long cylinder, which overlaps
    adjacent rows in small multistage stacks. Use mid-planes between neighboring
    stages, clamped by the duct when available.
    """
    stages = sorted(fan.stages, key=lambda stage: stage.axial_position_m)
    stage = _stage_for_zone(zone, stages)
    z = stage.axial_position_m if stage is not None else zone.origin[2]
    idx = stages.index(stage) if stage is not None else -1

    duct_start = 0.0
    duct_end = fan.duct.total_length_m if fan.duct is not None and fan.duct.enabled else None
    default_half_length = max(0.5 * fan.tip_radius_m, 0.005)

    if idx > 0:
        z_min = 0.5 * (stages[idx - 1].axial_position_m + z)
    elif duct_end is not None:
        z_min = 0.5 * (duct_start + z)
    else:
        z_min = z - default_half_length

    if idx >= 0 and idx < len(stages) - 1:
        z_max = 0.5 * (z + stages[idx + 1].axial_position_m)
    elif duct_end is not None:
        z_max = 0.5 * (z + duct_end)
    else:
        z_max = z + default_half_length

    if duct_end is not None:
        z_min = max(duct_start, z_min)
        z_max = min(duct_end, z_max)

    min_length = min(0.004, fan.tip_radius_m * 0.2)
    if z_max - z_min < min_length:
        midpoint = 0.5 * (z_min + z_max)
        z_min = midpoint - 0.5 * min_length
        z_max = midpoint + 0.5 * min_length
        if duct_end is not None:
            if z_min < duct_start:
                z_max += duct_start - z_min
                z_min = duct_start
            if z_max > duct_end:
                z_min -= z_max - duct_end
                z_max = duct_end

    return z_min, z_max


def _stage_for_zone(zone: "MRFZone", stages: "list[StageConfig]") -> "StageConfig | None":
    expected_cell_zone = zone.cell_zone
    for stage in stages:
        if expected_cell_zone == f"{stage.name}_zone":
            return stage
    return None
