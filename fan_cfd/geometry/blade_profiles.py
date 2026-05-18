"""
fan_cfd.geometry.blade_profiles
================================
Airfoil profile generation and radial-distribution profile evaluation.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from scipy.interpolate import interp1d

if TYPE_CHECKING:
    from fan_cfd.config import Profile, StageConfig


# ---------------------------------------------------------------------------
# NACA 4-digit airfoil
# ---------------------------------------------------------------------------


def naca4digit(code: str, n_points: int = 100) -> np.ndarray:
    """
    Generate NACA 4-digit airfoil (x, y) coordinates, normalized to chord = 1.

    Parameters
    ----------
    code : str
        NACA code string, e.g. ``"naca4412"`` or ``"4412"``.
    n_points : int
        Number of points along the upper + lower surface (each).

    Returns
    -------
    np.ndarray, shape (2*n_points - 1, 2)
        Coordinates starting at trailing edge, going over the top,
        around the leading edge, and back along the bottom to the trailing edge.
        Closed loop (first ≈ last).
    """
    # Parse code
    digits = code.lower().replace("naca", "").strip()
    if len(digits) == 4 and digits.isdigit():
        m = int(digits[0]) / 100.0
        p = int(digits[1]) / 10.0
        t = int(digits[2:]) / 100.0
    else:
        raise ValueError(f"Unsupported airfoil code: '{code}'. Use NACA 4-digit, e.g. 'naca4412'.")

    # Cosine spacing for better leading-edge resolution
    beta = np.linspace(0, math.pi, n_points)
    x = 0.5 * (1.0 - np.cos(beta))  # [0 .. 1]

    # Thickness distribution (Eq. 4-digit series)
    yt = (
        5
        * t
        * (
            0.2969 * np.sqrt(np.maximum(x, 0.0))
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
    )

    # Mean camber line and gradient
    yc = np.zeros_like(x)
    dyc_dx = np.zeros_like(x)
    if 0.0 < p < 1.0:
        fore = x < p
        aft = ~fore
        yc[fore] = m / p**2 * (2 * p * x[fore] - x[fore] ** 2)
        yc[aft] = m / (1 - p) ** 2 * (
            (1 - 2 * p) + 2 * p * x[aft] - x[aft] ** 2
        )
        dyc_dx[fore] = 2 * m / p**2 * (p - x[fore])
        dyc_dx[aft] = 2 * m / (1 - p) ** 2 * (p - x[aft])

    theta = np.arctan(dyc_dx)

    # Upper and lower surface
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    # Build closed contour: TE → upper → LE → lower → TE
    x_upper = xu[::-1]  # trailing edge to leading edge
    y_upper = yu[::-1]
    x_lower = xl[1:]    # leading edge to trailing edge (skip LE duplicate)
    y_lower = yl[1:]

    x_all = np.concatenate([x_upper, x_lower])
    y_all = np.concatenate([y_upper, y_lower])
    x_all = np.clip(x_all, 0.0, 1.0)

    return np.column_stack([x_all, y_all])


def naca4digit_upper_lower(code: str, n_points: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """
    Return upper and lower surface separately as (n, 2) arrays [x, y].
    Useful for lofting where you need separate pressure/suction sides.
    """
    digits = code.lower().replace("naca", "").strip()
    if len(digits) == 4 and digits.isdigit():
        m = int(digits[0]) / 100.0
        p = int(digits[1]) / 10.0
        t = int(digits[2:]) / 100.0
    else:
        raise ValueError(f"Unsupported airfoil code: '{code}'")

    beta = np.linspace(0, math.pi, n_points)
    x = 0.5 * (1.0 - np.cos(beta))

    yt = (
        5
        * t
        * (
            0.2969 * np.sqrt(np.maximum(x, 0.0))
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
    )

    if p > 0.0:
        yc = np.where(
            x < p,
            m / p**2 * (2 * p * x - x**2),
            m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2),
        )
        dyc_dx = np.where(
            x < p,
            2 * m / p**2 * (p - x),
            2 * m / (1 - p) ** 2 * (p - x),
        )
    else:
        yc = np.zeros_like(x)
        dyc_dx = np.zeros_like(x)

    theta = np.arctan(dyc_dx)

    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)
    xu = np.clip(xu, 0.0, 1.0)
    xl = np.clip(xl, 0.0, 1.0)

    upper = np.column_stack([xu, yu])
    lower = np.column_stack([xl, yl])
    return upper, lower


# ---------------------------------------------------------------------------
# Profile evaluation
# ---------------------------------------------------------------------------


def interpolate_profile(profile: "Profile", r_normalized: float) -> float:
    """
    Evaluate a chord or twist Profile at a normalized radial position r ∈ [0, 1].

    For ``CONSTANT``: returns ``profile.value``.
    For ``LINEAR``: linearly interpolates between the two end points.
    For ``CONTROL_POINTS``: cubic-spline interpolates through the control points.
    For ``INHERIT``: should have been resolved before calling this; raises if not.

    Parameters
    ----------
    profile : Profile
    r_normalized : float
        Radial position normalized by blade span, in [0, 1].

    Returns
    -------
    float
    """
    from fan_cfd.config import ProfileType

    r = float(np.clip(r_normalized, 0.0, 1.0))

    if profile.type == ProfileType.CONSTANT:
        return float(profile.value)  # type: ignore[arg-type]

    if profile.type in (ProfileType.LINEAR, ProfileType.CONTROL_POINTS):
        pts = np.array(profile.points)  # (n, 2)  [r, value]
        r_pts = pts[:, 0]
        v_pts = pts[:, 1]
        if profile.type == ProfileType.LINEAR or len(pts) == 2:
            # Simple linear interpolation
            return float(np.interp(r, r_pts, v_pts))
        # Cubic spline for control points
        kind = "cubic" if len(pts) >= 4 else "linear"
        f = interp1d(r_pts, v_pts, kind=kind, fill_value="extrapolate")
        return float(f(r))

    if profile.type == ProfileType.INHERIT:
        raise RuntimeError(
            "Profile type INHERIT must be resolved before calling interpolate_profile. "
            "Call resolve_inherited_profiles() first."
        )

    raise ValueError(f"Unknown profile type: {profile.type}")


def apply_profile_scale(profile: "Profile", scale: float) -> "Profile":
    """Return a new Profile with all values multiplied by *scale*."""
    from fan_cfd.config import Profile, ProfileType

    if profile.type == ProfileType.INHERIT:
        raise RuntimeError(
            "Cannot scale an unresolved INHERIT profile. "
            "Call resolve_inherited_profiles() before scaling."
        )

    if profile.type == ProfileType.CONSTANT:
        return Profile(type=ProfileType.CONSTANT, value=profile.value * scale)

    if profile.type in (ProfileType.LINEAR, ProfileType.CONTROL_POINTS):
        new_points = [(r, v * scale) for r, v in profile.points]
        return Profile(type=profile.type, points=new_points)

    raise ValueError(f"Unknown profile type: {profile.type}")
