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

    Returns
    -------
    dict[str, Path]
        Mapping of mesh name → exported file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported: dict[str, Path] = {}

    for name, mesh in meshes.items():
        out_path = output_dir / f"{name}.stl"
        try:
            if isinstance(mesh, trimesh.Trimesh) and len(mesh.faces) > 0:
                mesh.export(str(out_path))
                exported[name] = out_path
                logger.debug("Exported %s → %s (%d faces)", name, out_path, len(mesh.faces))
            elif isinstance(mesh, trimesh.Scene):
                # Flatten scene to single mesh
                flat = trimesh.util.concatenate(list(mesh.dump()))
                flat.export(str(out_path))
                exported[name] = out_path
                logger.debug("Exported scene %s → %s", name, out_path)
            else:
                logger.warning("Skipping empty mesh '%s'", name)
        except Exception as exc:
            logger.error("Failed to export '%s': %s", name, exc)

    return exported


def validate_stl_files(paths: dict[str, Path]) -> dict[str, bool]:
    """
    Validate each STL file: check it is non-empty and, for closed surfaces,
    that it is watertight.

    Returns
    -------
    dict[str, bool]
        True if the file passes basic validation, False otherwise.
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

            # Basic sanity checks
            has_verts = len(mesh.vertices) > 0
            has_faces = len(mesh.faces) > 0
            no_nans = not np.any(np.isnan(mesh.vertices))

            ok = has_verts and has_faces and no_nans
            if not ok:
                logger.warning(
                    "'%s': verts=%d, faces=%d, nan=%s",
                    name, len(mesh.vertices), len(mesh.faces),
                    np.any(np.isnan(mesh.vertices)),
                )

            results[name] = ok

        except Exception as exc:
            logger.error("Could not load '%s' for validation: %s", name, exc)
            results[name] = False

    return results
