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
    from fan_cfd.config import FanConfig
    from fan_cfd.openfoam.mrf_zones import MRFZone


def write_topo_set_dict(zones: "list[MRFZone]", fan: "FanConfig", output_path: Path) -> None:
    """
    Write a ``topoSetDict`` that creates a cylindrical cell zone for each MRF zone.

    The cylinders are sized to contain each rotor stage's swept volume.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tip_r = fan.tip_radius_m
    hub_r = fan.hub_radius_m

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
        z_min = zone.origin[2] - 0.01
        z_max = zone.origin[2] + 0.05  # approximate axial extent of one blade row
        action_lines += [
            "    {",
            f"        name    {zone.cell_zone};",
            "        type    cellZoneSet;",
            "        action  new;",
            "        source  cylinderToCell;",
            f"        p1      ({zone.origin[0]} {zone.origin[1]} {z_min});",
            f"        p2      ({zone.origin[0]} {zone.origin[1]} {z_max});",
            f"        radius  {tip_r * 1.05:.6f};",
            "    }",
            "",
        ]

    output_path.write_text(header + "\n".join(action_lines) + footer)
