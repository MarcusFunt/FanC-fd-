"""
fan_cfd.geometry.cad_export
============================
STL file export and validation for generated fan geometry.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from fan_cfd.utils.logging_utils import get_logger

logger = get_logger(__name__)

_MIN_PRINT_VOLUME_M3 = 1e-15


def _as_trimesh(mesh: trimesh.Trimesh | trimesh.Scene) -> trimesh.Trimesh:
    """Return a Trimesh from a mesh or a flattened scene."""
    if isinstance(mesh, trimesh.Trimesh):
        return mesh
    if isinstance(mesh, trimesh.Scene):
        dumped = mesh.dump()
        geometries = list(dumped) if not isinstance(dumped, trimesh.Trimesh) else [dumped]
        if not geometries:
            return trimesh.Trimesh()
        return trimesh.util.concatenate(geometries)
    raise TypeError(f"Unsupported mesh type: {type(mesh)!r}")


def printability_issues(mesh: trimesh.Trimesh | trimesh.Scene) -> list[str]:
    """
    Return reasons a mesh is not suitable for direct STL 3D printing.

    Exported geometry must be a finite, watertight, consistently wound,
    positive-volume solid.
    """
    try:
        candidate = _as_trimesh(mesh)
    except TypeError as exc:
        return [str(exc)]

    issues: list[str] = []
    if len(candidate.vertices) == 0:
        issues.append("has no vertices")
    if len(candidate.faces) == 0:
        issues.append("has no faces")
    if len(candidate.vertices) and not np.all(np.isfinite(candidate.vertices)):
        issues.append("has non-finite vertices")
    if len(candidate.faces) and not np.all(np.isfinite(candidate.faces)):
        issues.append("has non-finite faces")
    if len(candidate.vertices) and np.any(np.isnan(candidate.vertices)):
        issues.append("has NaN vertices")

    if not issues:
        if not candidate.is_watertight:
            issues.append("is not watertight")
        if not candidate.is_winding_consistent:
            issues.append("has inconsistent face winding")

        volume = candidate.volume
        if not np.isfinite(volume) or abs(volume) <= _MIN_PRINT_VOLUME_M3:
            issues.append("has no positive printable volume")
        elif not candidate.is_volume:
            issues.append("is not a positive closed volume")

    return issues


def is_3d_printable_mesh(mesh: trimesh.Trimesh | trimesh.Scene) -> bool:
    """Return True when *mesh* passes the STL printability checks."""
    return not printability_issues(mesh)


def prepare_mesh_for_3d_printing(
    mesh: trimesh.Trimesh | trimesh.Scene,
    name: str = "mesh",
) -> trimesh.Trimesh:
    """
    Make a defensive copy, normalize normals, and verify STL printability.

    Raises
    ------
    ValueError
        If the mesh is not a watertight positive-volume solid after cleanup.
    """
    printable = _as_trimesh(mesh).copy()
    printable.remove_unreferenced_vertices()
    printable.fix_normals()
    printable.remove_unreferenced_vertices()

    issues = printability_issues(printable)
    if not issues:
        return printable

    repaired = printable.copy()
    repaired.merge_vertices(digits_vertex=12)
    repaired.fix_normals()
    repaired.remove_unreferenced_vertices()

    repaired_issues = printability_issues(repaired)
    if repaired_issues:
        raise ValueError(
            f"Mesh '{name}' is not 3D-printable: {', '.join(repaired_issues)}"
        )
    return repaired


def export_stl_files(
    meshes: dict[str, trimesh.Trimesh],
    output_dir: Path,
    ascii_format: bool = False,
) -> dict[str, Path]:
    """
    Export each mesh to a separate STL file in *output_dir*.

    Parameters
    ----------
    meshes : dict[str, trimesh.Trimesh]
        Named mesh objects to export.
    output_dir : Path
        Directory where STL files will be written (created if needed).
    ascii_format : bool
        Write ASCII STL instead of binary. Default: binary (smaller files).
        All meshes are validated as 3D-printable solids before export.

    Returns
    -------
    dict[str, Path]
        Mapping of mesh name to exported file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported: dict[str, Path] = {}

    for name, mesh in meshes.items():
        out_path = output_dir / f"{name}.stl"
        try:
            printable_mesh = prepare_mesh_for_3d_printing(mesh, name)
            if len(printable_mesh.faces) > 0:
                file_type = "stl_ascii" if ascii_format else "stl"
                printable_mesh.export(str(out_path), file_type=file_type)
                exported[name] = out_path
                logger.debug(
                    "Exported printable %s -> %s (%d faces)",
                    name,
                    out_path,
                    len(printable_mesh.faces),
                )
            else:
                logger.warning("Skipping empty mesh '%s'", name)
        except Exception as exc:
            logger.error("Failed to export '%s': %s", name, exc)
            raise

    return exported


def validate_stl_files(paths: dict[str, Path]) -> dict[str, bool]:
    """
    Validate each STL file for direct 3D-printable solid geometry.

    Returns
    -------
    dict[str, bool]
        True if the file passes printability validation, False otherwise.
    """
    results: dict[str, bool] = {}

    for name, path in paths.items():
        path = Path(path)
        if not path.exists():
            logger.warning("STL not found: %s", path)
            results[name] = False
            continue

        if path.stat().st_size == 0:
            logger.warning("STL is empty: %s", path)
            results[name] = False
            continue

        try:
            mesh = trimesh.load(str(path), force="mesh")
            if not isinstance(mesh, trimesh.Trimesh):
                logger.warning("'%s' loaded as non-Trimesh type: %s", name, type(mesh))
                results[name] = False
                continue

            issues = printability_issues(mesh)
            ok = not issues
            if issues:
                logger.warning("'%s' is not 3D-printable: %s", name, ", ".join(issues))
            results[name] = ok

        except Exception as exc:
            logger.error("Could not load '%s' for validation: %s", name, exc)
            results[name] = False

    return results
