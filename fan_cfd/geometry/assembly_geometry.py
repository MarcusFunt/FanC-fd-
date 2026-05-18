"""
fan_cfd.geometry.assembly_geometry
====================================
Generates hub, duct, and the full assembled fan geometry from FanConfig.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import trimesh

from fan_cfd.geometry.stage_geometry import generate_stage_geometry
from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig, StageConfig

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Hub
# ---------------------------------------------------------------------------


def generate_hub(fan: "FanConfig") -> trimesh.Trimesh:
    """
    Generate a cylindrical hub mesh that spans the full stage assembly.

    The hub extends axially from the first stage position minus a small
    margin to the last stage position plus a small margin.
    """
    hub_r = fan.hub_radius_m
    if not fan.stages:
        axial_start = 0.0
        axial_end = hub_r * 4.0
    else:
        positions = [s.axial_position_m for s in fan.stages]
        margin = 0.01
        axial_start = min(positions) - margin
        axial_end = max(positions) + margin + 0.05  # +chord approx

    height = axial_end - axial_start

    # Create using trimesh cylinder primitive, then translate
    cyl = trimesh.creation.cylinder(radius=hub_r, height=height, sections=64)

    # Cylinder is centered at origin; shift so bottom is at axial_start
    T = trimesh.transformations.translation_matrix([0, 0, axial_start + height / 2.0])
    cyl.apply_transform(T)

    # The cylinder axis from trimesh is Z; our axial direction is also Z → correct
    return cyl


# ---------------------------------------------------------------------------
# Duct
# ---------------------------------------------------------------------------


def generate_duct(fan: "FanConfig") -> trimesh.Trimesh | None:
    """
    Generate an annular duct (hollow cylinder) surrounding the fan assembly.
    Returns None if no duct is configured or duct.enabled is False.
    """
    if fan.duct is None or not fan.duct.enabled:
        return None

    duct = fan.duct
    inner_r = duct.inner_radius_m
    outer_r = inner_r + duct.wall_thickness_m
    length = duct.total_length_m

    # Build hollow cylinder as outer - inner tubes with end caps
    outer_cyl = trimesh.creation.cylinder(radius=outer_r, height=length, sections=128)
    inner_cyl = trimesh.creation.cylinder(radius=inner_r, height=length + 1e-4, sections=128)

    # Boolean difference: outer - inner
    try:
        duct_mesh = outer_cyl.difference(inner_cyl)
    except Exception:
        # Fallback if boolean fails: just use outer cylinder
        logger.warning("Boolean difference for duct failed; using solid outer cylinder")
        duct_mesh = outer_cyl

    # Position so duct spans from z=0 to z=length
    T = trimesh.transformations.translation_matrix([0, 0, length / 2.0])
    duct_mesh.apply_transform(T)

    return duct_mesh


# ---------------------------------------------------------------------------
# Full assembly
# ---------------------------------------------------------------------------


def generate_full_assembly(
    fan: "FanConfig",
    stages: list["StageConfig"],
) -> dict[str, trimesh.Trimesh]:
    """
    Generate and collect all geometry components.

    Returns
    -------
    dict[str, trimesh.Trimesh]
        Keys include: ``rotor_1``, ``stator_1``, ..., ``hub``, ``duct``
        (if enabled), ``all_rotors``, ``all_stators``, ``full_assembly``.
    """
    meshes: dict[str, trimesh.Trimesh] = {}
    all_rotor_blades: list[trimesh.Trimesh] = []
    all_stator_blades: list[trimesh.Trimesh] = []
    rotor_idx = 0
    stator_idx = 0

    for stage in stages:
        blades = generate_stage_geometry(stage, fan)
        blade_mesh = trimesh.util.concatenate(blades) if blades else trimesh.Trimesh()

        from fan_cfd.config import StageType

        if stage.type == StageType.ROTOR:
            rotor_idx += 1
            key = f"rotor_{rotor_idx}"
            all_rotor_blades.extend(blades)
        else:
            stator_idx += 1
            key = f"stator_{stator_idx}"
            all_stator_blades.extend(blades)

        meshes[key] = blade_mesh
        logger.info("  [%s] %s: %d vertices, %d faces", key, stage.name,
                    len(blade_mesh.vertices), len(blade_mesh.faces))

    # Hub
    hub_mesh = generate_hub(fan)
    meshes["hub"] = hub_mesh
    logger.info("  [hub]: %d vertices, %d faces", len(hub_mesh.vertices), len(hub_mesh.faces))

    # Duct
    duct_mesh = generate_duct(fan)
    if duct_mesh is not None:
        meshes["duct"] = duct_mesh
        logger.info("  [duct]: %d vertices, %d faces",
                    len(duct_mesh.vertices), len(duct_mesh.faces))

    # Combined meshes
    if all_rotor_blades:
        meshes["all_rotors"] = trimesh.util.concatenate(all_rotor_blades)
    if all_stator_blades:
        meshes["all_stators"] = trimesh.util.concatenate(all_stator_blades)

    all_parts = list(meshes.values())
    if all_parts:
        meshes["full_assembly"] = trimesh.util.concatenate(all_parts)

    return meshes
