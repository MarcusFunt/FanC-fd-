"""
fan_cfd.geometry.fan_geometry
==============================
High-level convenience wrappers that orchestrate geometry generation
for a complete FanCFDConfig.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import trimesh

from fan_cfd.geometry.assembly_geometry import generate_full_assembly
from fan_cfd.geometry.cad_export import export_stl_files, validate_stl_files
from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import FanCFDConfig

logger = get_logger(__name__)


def build_geometry(config: "FanCFDConfig") -> dict[str, trimesh.Trimesh]:
    """
    Generate complete fan geometry from config.

    Returns
    -------
    dict[str, trimesh.Trimesh]
        Named meshes: rotor_1, stator_1, hub, duct, full_assembly, etc.
    """
    logger.info("Building geometry for fan '%s'", config.fan.name)
    meshes = generate_full_assembly(config.fan, config.fan.stages)
    logger.info("Generated %d mesh components", len(meshes))
    return meshes


def build_and_export_geometry(
    config: "FanCFDConfig",
    output_dir: Path,
) -> dict[str, Path]:
    """
    Build geometry and export all components as STL files.

    Returns
    -------
    dict[str, Path]
        name → path mapping for all exported STL files.
    """
    meshes = build_geometry(config)
    stl_paths = export_stl_files(meshes, output_dir)

    validations = validate_stl_files(stl_paths)
    for name, ok in validations.items():
        if ok:
            logger.info("  ✓ %s.stl validated", name)
        else:
            logger.warning("  ✗ %s.stl FAILED validation", name)

    return stl_paths
