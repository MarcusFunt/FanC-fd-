"""
fan_cfd.geometry.stage_geometry
================================
Per-stage 3D blade geometry generation.

Approach
--------
For each blade:
1. Generate N radial cross-section airfoil profiles (2D, normalized chord=1).
2. At each section radius r:
   - Scale by chord(r)
   - Rotate in-plane by twist(r) degrees
   - Optionally offset by rake and skew
   - Transform to 3D: x_axial = axial_position + rake_offset,
                       y_radial = r * cos(blade_angle),
                       z_radial = r * sin(blade_angle)
3. Loft consecutive sections into a ruled (triangle-strip) surface.
4. Cap root and tip with triangle fans.
5. Rotate the single blade N times around the axis for blade_count.

The result is a list of trimesh.Trimesh objects (one per blade).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import trimesh

from fan_cfd.geometry.blade_profiles import (
    interpolate_profile,
    naca4digit_upper_lower,
)
from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig, StageConfig

logger = get_logger(__name__)

# Number of airfoil surface points per side (upper/lower)
_PROFILE_POINTS = 32


def _make_section_3d(
    airfoil_code: str,
    chord: float,
    twist_deg: float,
    radius: float,
    axial_pos: float,
    rake: float = 0.0,
    skew_deg: float = 0.0,
    thickness_scale: float = 1.0,
    n_pts: int = _PROFILE_POINTS,
) -> np.ndarray:
    """
    Build a single radial cross-section as a 3D point cloud.

    The blade axis is the global Z-axis (axial direction).
    At radius *r*, the section is positioned in the X-Z plane (blade_angle=0).
    The caller rotates around Z to distribute blades angularly.

    Returns
    -------
    np.ndarray, shape (2*n_pts, 3)
        3D vertices of the airfoil section: upper side then lower side.
    """
    upper_2d, lower_2d = naca4digit_upper_lower(airfoil_code, n_points=n_pts)

    # Apply thickness scale to Y (camber direction)
    upper_2d[:, 1] *= thickness_scale
    lower_2d[:, 1] *= thickness_scale

    # Scale by chord (airfoil normalized to chord=1)
    upper_2d *= chord
    lower_2d *= chord

    # Rotate by twist angle (rotation around chord-line midpoint ≈ x=0.25c)
    pivot_x = 0.25 * chord
    twist_rad = math.radians(twist_deg)
    cos_t, sin_t = math.cos(twist_rad), math.sin(twist_rad)

    def rotate_2d(pts: np.ndarray) -> np.ndarray:
        ox = pts[:, 0] - pivot_x
        oy = pts[:, 1]
        rx = ox * cos_t - oy * sin_t + pivot_x
        ry = ox * sin_t + oy * cos_t
        return np.column_stack([rx, ry])

    upper_2d = rotate_2d(upper_2d)
    lower_2d = rotate_2d(lower_2d)

    # Map 2D (chord-x, camber-y) → 3D (axial-Z, radial-X, tangential-Y=0)
    # chord direction → axial (Z)
    # camber direction → tangential (Y)
    # radial (X) = constant radius for this section
    def to_3d(pts_2d: np.ndarray) -> np.ndarray:
        z_ax = axial_pos + rake + pts_2d[:, 0]  # axial = chord direction + rake
        x_rad = np.full(len(pts_2d), radius)
        y_tan = pts_2d[:, 1]  # camber → tangential
        return np.column_stack([x_rad, y_tan, z_ax])

    upper_3d = to_3d(upper_2d)
    lower_3d = to_3d(lower_2d)

    # Apply skew (angular offset at this section)
    if abs(skew_deg) > 1e-9:
        skew_rad = math.radians(skew_deg)
        # Rotate section points around the Z-axis by skew_rad
        cos_s, sin_s = math.cos(skew_rad), math.sin(skew_rad)
        for pts in (upper_3d, lower_3d):
            x = pts[:, 0].copy()
            y = pts[:, 1].copy()
            pts[:, 0] = x * cos_s - y * sin_s
            pts[:, 1] = x * sin_s + y * cos_s

    return np.vstack([upper_3d, lower_3d])


def _loft_sections(sections: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """
    Create a ruled surface between consecutive airfoil sections.

    Each section is shape (2*N, 3) where upper=[0:N], lower=[N:2N].

    Returns
    -------
    vertices : np.ndarray, shape (V, 3)
    faces    : np.ndarray, shape (F, 3)
    """
    all_verts: list[np.ndarray] = []
    all_faces: list[np.ndarray] = []
    v_offset = 0
    n_sec = len(sections)
    n_pts = len(sections[0]) // 2  # points per side

    for i in range(n_sec):
        all_verts.append(sections[i])

    # Build triangle strips between consecutive sections
    for i in range(n_sec - 1):
        base = i * (2 * n_pts)
        next_base = (i + 1) * (2 * n_pts)
        for j in range(2 * n_pts - 1):
            v0 = base + j
            v1 = base + j + 1
            v2 = next_base + j
            v3 = next_base + j + 1
            all_faces.append([v0, v1, v2])
            all_faces.append([v1, v3, v2])

    vertices = np.vstack(all_verts)
    faces = np.array(all_faces, dtype=np.int32)
    return vertices, faces


def _cap_section(
    section: np.ndarray, center: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cap an open cross-section ring with a triangle fan.

    Parameters
    ----------
    section : np.ndarray, shape (2*N, 3)
        The boundary vertices of the cap.
    center : np.ndarray, shape (3,)
        The center point of the cap.

    Returns
    -------
    vertices : np.ndarray, shape (2*N+1, 3)
    faces    : np.ndarray, shape (2*N, 3)
    """
    n = len(section)
    verts = np.vstack([section, center[np.newaxis, :]])
    center_idx = n
    faces = []
    for j in range(n):
        faces.append([j, (j + 1) % n, center_idx])
    return verts, np.array(faces, dtype=np.int32)


def generate_single_blade(
    stage: "StageConfig",
    fan: "FanConfig",
) -> trimesh.Trimesh:
    """
    Generate geometry for a single blade (blade index 0).
    Caller rotates this around Z to get all blades.
    """
    blade_cfg = stage.blade
    hub_r = fan.hub_radius_m
    tip_r = fan.tip_radius_m
    span = tip_r - hub_r
    n_sec = blade_cfg.radial_sections
    axial_pos = stage.axial_position_m

    sections: list[np.ndarray] = []

    for i in range(n_sec):
        r_norm = i / (n_sec - 1)
        radius = hub_r + r_norm * span

        chord = interpolate_profile(blade_cfg.chord_profile, r_norm)
        twist_deg = interpolate_profile(blade_cfg.twist_profile_deg, r_norm)

        rake = 0.0
        if blade_cfg.rake_profile is not None:
            rake = interpolate_profile(blade_cfg.rake_profile, r_norm)

        skew_deg = 0.0
        if blade_cfg.skew_profile is not None:
            skew_deg = interpolate_profile(blade_cfg.skew_profile, r_norm)

        sec_3d = _make_section_3d(
            airfoil_code=blade_cfg.airfoil,
            chord=chord,
            twist_deg=twist_deg,
            radius=radius,
            axial_pos=axial_pos,
            rake=rake,
            skew_deg=skew_deg,
            thickness_scale=blade_cfg.thickness_scale,
        )
        sections.append(sec_3d)

    verts, faces = _loft_sections(sections)

    # Cap at root (hub radius)
    root_center = np.array([hub_r, 0.0, axial_pos])
    cap_verts_root, cap_faces_root = _cap_section(sections[0], root_center)
    offset_root = len(verts)
    cap_faces_root_shifted = cap_faces_root + offset_root

    # Cap at tip
    tip_center = np.array([tip_r, 0.0, axial_pos])
    cap_verts_tip, cap_faces_tip = _cap_section(sections[-1], tip_center)
    offset_tip = len(verts) + len(cap_verts_root)
    cap_faces_tip_shifted = cap_faces_tip + offset_tip

    all_verts = np.vstack([verts, cap_verts_root, cap_verts_tip])
    all_faces = np.vstack([faces, cap_faces_root_shifted, cap_faces_tip_shifted])

    mesh = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=True)
    return mesh


def _rotate_mesh_around_z(mesh: trimesh.Trimesh, angle_rad: float) -> trimesh.Trimesh:
    """Return a copy of *mesh* rotated around the Z (axial) axis."""
    T = trimesh.transformations.rotation_matrix(angle_rad, [0, 0, 1])
    rotated = mesh.copy()
    rotated.apply_transform(T)
    return rotated


def generate_stage_geometry(
    stage: "StageConfig",
    fan: "FanConfig",
    resolved_stages: dict | None = None,
) -> list[trimesh.Trimesh]:
    """
    Generate 3D blade geometry for one stage.

    Returns a list of ``trimesh.Trimesh`` objects, one per blade.

    Parameters
    ----------
    stage : StageConfig
    fan : FanConfig
    resolved_stages : dict, optional
        Pre-resolved stage data (unused directly; blade profiles must already
        be resolved before calling this function).
    """
    logger.debug(
        "Generating stage '%s' (%d blades, %s)",
        stage.name,
        stage.blade_count,
        stage.type,
    )

    single_blade = generate_single_blade(stage, fan)

    blades: list[trimesh.Trimesh] = []
    for k in range(stage.blade_count):
        angle = 2.0 * math.pi * k / stage.blade_count
        blade = _rotate_mesh_around_z(single_blade, angle)
        blades.append(blade)

    logger.debug("  Generated %d blades for stage '%s'", len(blades), stage.name)
    return blades
