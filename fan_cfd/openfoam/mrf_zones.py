"""
fan_cfd.openfoam.mrf_zones
===========================
MRF (Multiple Reference Frame) zone generation for OpenFOAM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fan_cfd.utils.names import openfoam_identifier

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig


@dataclass
class MRFZone:
    """Data for one OpenFOAM MRF zone (one rotor stage)."""

    zone_name: str          # e.g. "rotor_1_MRF"
    cell_zone: str          # e.g. "rotor_1_zone"
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    omega_rad_s: float = 0.0
    nonRotating_patches: list[str] = field(default_factory=list)

    @property
    def omega_signed(self) -> float:
        """Positive = CCW (right-hand rule), negative = CW."""
        return self.omega_rad_s

    @property
    def rpm(self) -> float:
        return self.omega_rad_s * 60.0 / (2.0 * math.pi)


def build_mrf_zones(fan: "FanConfig") -> list[MRFZone]:
    """
    Build one MRFZone per rotor stage.

    Parameters
    ----------
    fan : FanConfig

    Returns
    -------
    list[MRFZone]
    """
    zones: list[MRFZone] = []

    for stage in fan.rotor_stages:
        rpm = stage.rpm or fan.rpm
        omega = rpm * 2.0 * math.pi / 60.0
        # Apply rotation direction sign
        if stage.rotation_direction == "clockwise":
            omega = -omega

        non_rotating_patches = ["inlet", "outlet", "sides", "hub"]
        if fan.duct is not None and fan.duct.enabled:
            non_rotating_patches.append("duct")
        non_rotating_patches.extend(openfoam_identifier(s.name, "stage") for s in fan.stator_stages)
        patch_name = openfoam_identifier(stage.name, "stage")

        zone = MRFZone(
            zone_name=f"{patch_name}_MRF",
            cell_zone=f"{patch_name}_zone",
            axis=(0.0, 0.0, 1.0),
            origin=(0.0, 0.0, stage.axial_position_m),
            omega_rad_s=omega,
            nonRotating_patches=non_rotating_patches,
        )
        zones.append(zone)

    return zones


def write_mrf_properties(zones: list[MRFZone], output_path: Path) -> None:
    """
    Write OpenFOAM ``MRFProperties`` dictionary.

    Parameters
    ----------
    zones : list[MRFZone]
    output_path : Path
        Destination file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "/*--------------------------------*- C++ -*----------------------------------*\\",
        "| =========                 |                                                 |",
        "| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |",
        "|  \\\\    /   O peration     | Version:  v2206                                 |",
        "|   \\\\  /    A nd           | Web:      www.OpenFOAM.com                      |",
        "|    \\\\/     M anipulation  |                                                 |",
        "\\*---------------------------------------------------------------------------*/",
        "FoamFile",
        "{",
        "    version     2.0;",
        "    format      ascii;",
        "    class       dictionary;",
        "    location    \"constant\";",
        "    object      MRFProperties;",
        "}",
        "// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //",
        "",
    ]

    for zone in zones:
        non_rotating_str = " ".join(zone.nonRotating_patches)
        lines += [
            f"{zone.zone_name}",
            "{",
            f"    cellZone        {zone.cell_zone};",
            "    active          yes;",
            f"    nonRotatingPatches ( {non_rotating_str} );",
            f"    origin          ({zone.origin[0]} {zone.origin[1]} {zone.origin[2]});",
            f"    axis            ({zone.axis[0]} {zone.axis[1]} {zone.axis[2]});",
            f"    omega           {zone.omega_signed:.6f};  // rad/s  ({zone.rpm:.1f} RPM)",
            "}",
            "",
        ]

    lines += [
        "// ************************************************************************* //",
    ]

    output_path.write_text("\n".join(lines))
