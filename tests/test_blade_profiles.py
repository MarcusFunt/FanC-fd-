"""
tests/test_blade_profiles.py
==============================
Tests for airfoil generation and radial profile interpolation.
"""

import math

import numpy as np
import pytest

from fan_cfd.config import Profile, ProfileType
from fan_cfd.geometry.blade_profiles import (
    apply_profile_scale,
    interpolate_profile,
    naca4digit,
    naca4digit_upper_lower,
    resolve_inherited_profile,
)


# ---------------------------------------------------------------------------
# NACA 4-digit
# ---------------------------------------------------------------------------


class TestNaca4Digit:
    def test_output_shape(self):
        coords = naca4digit("naca4412", n_points=50)
        assert coords.ndim == 2
        assert coords.shape[1] == 2
        assert len(coords) == 2 * 50 - 1  # upper + lower merged at LE

    def test_trailing_edge_starts_at_one(self):
        coords = naca4digit("naca4412", n_points=64)
        # Trailing edge is at x=1.0
        assert abs(coords[0, 0] - 1.0) < 0.01

    def test_leading_edge_near_zero(self):
        coords = naca4digit("naca4412", n_points=64)
        # Leading edge should be near x=0
        x_vals = coords[:, 0]
        assert min(x_vals) < 0.02

    def test_naca0012_symmetric(self):
        """NACA 0012 should be symmetric about y=0 (zero camber)."""
        upper, lower = naca4digit_upper_lower("naca0012", n_points=50)
        # At same x positions, upper and lower y should be equal and opposite
        # (after accounting for cosine spacing differences)
        # Check at x=0.5 approximately
        mid = len(upper) // 2
        x_u = upper[mid, 0]
        y_u = upper[mid, 1]
        y_l = lower[mid, 1]
        assert abs(y_u + y_l) < abs(y_u) * 0.1  # approximately symmetric

    def test_naca4412_has_camber(self):
        """NACA 4412 has m=4%, p=40% max camber; should not be symmetric."""
        upper, lower = naca4digit_upper_lower("naca4412", n_points=50)
        mid = len(upper) // 2
        y_u = upper[mid, 1]
        y_l = lower[mid, 1]
        # For cambered airfoil, |y_u| != |y_l|
        assert abs(y_u) != pytest.approx(abs(y_l), rel=0.05)

    def test_coordinates_normalized(self):
        """Chord should be normalized to 1 (x from 0 to 1)."""
        coords = naca4digit("naca4412", n_points=64)
        x_vals = coords[:, 0]
        assert max(x_vals) <= 1.0 + 1e-9
        assert min(x_vals) >= -1e-9

    def test_no_nans_in_coords(self):
        for code in ["naca0012", "naca2412", "naca4412", "naca6412"]:
            coords = naca4digit(code, n_points=64)
            assert not np.any(np.isnan(coords)), f"NaN in {code}"

    def test_bad_code_raises(self):
        with pytest.raises(ValueError):
            naca4digit("NACA_INVALID", n_points=50)

    def test_upper_lower_separate(self):
        upper, lower = naca4digit_upper_lower("naca4412", n_points=50)
        assert upper.shape == lower.shape == (50, 2)
        # Upper surface y should be predominantly positive
        assert np.mean(upper[:, 1]) > 0
        # Lower surface y should be predominantly negative
        assert np.mean(lower[:, 1]) < np.mean(upper[:, 1])


# ---------------------------------------------------------------------------
# Profile interpolation
# ---------------------------------------------------------------------------


class TestInterpolateProfile:
    def test_constant_profile(self):
        p = Profile.constant(30.0)
        for r in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert interpolate_profile(p, r) == pytest.approx(30.0)

    def test_linear_profile_at_endpoints(self):
        p = Profile.linear(40.0, 20.0)
        assert interpolate_profile(p, 0.0) == pytest.approx(40.0)
        assert interpolate_profile(p, 1.0) == pytest.approx(20.0)

    def test_linear_profile_at_midpoint(self):
        p = Profile.linear(40.0, 20.0)
        assert interpolate_profile(p, 0.5) == pytest.approx(30.0)

    def test_control_points_at_known_values(self):
        pts = [(0.0, 10.0), (0.5, 20.0), (1.0, 10.0)]
        p = Profile.control_points(pts)
        assert interpolate_profile(p, 0.0) == pytest.approx(10.0, abs=1e-6)
        assert interpolate_profile(p, 1.0) == pytest.approx(10.0, abs=1e-6)
        assert interpolate_profile(p, 0.5) == pytest.approx(20.0, abs=1e-3)

    def test_clamps_r_to_01(self):
        """Out-of-range r should be clamped to [0, 1]."""
        p = Profile.linear(10.0, 20.0)
        assert interpolate_profile(p, -0.5) == pytest.approx(10.0)
        assert interpolate_profile(p, 1.5) == pytest.approx(20.0)

    def test_inherit_raises(self):
        p = Profile(type=ProfileType.INHERIT, from_stage="rotor_1")
        with pytest.raises(RuntimeError, match="INHERIT"):
            interpolate_profile(p, 0.5)


# ---------------------------------------------------------------------------
# Profile scale
# ---------------------------------------------------------------------------


class TestApplyProfileScale:
    def test_scale_constant(self):
        p = Profile.constant(0.03)
        scaled = apply_profile_scale(p, 0.9)
        assert scaled.value == pytest.approx(0.027)

    def test_scale_linear(self):
        p = Profile.linear(40.0, 20.0)
        scaled = apply_profile_scale(p, 0.5)
        assert scaled.points[0][1] == pytest.approx(20.0)
        assert scaled.points[1][1] == pytest.approx(10.0)

    def test_scale_control_points(self):
        pts = [(0.0, 10.0), (0.5, 20.0), (1.0, 10.0)]
        p = Profile.control_points(pts)
        scaled = apply_profile_scale(p, 2.0)
        assert scaled.points[1][1] == pytest.approx(40.0)

    def test_scale_one_unchanged(self):
        p = Profile.constant(30.0)
        scaled = apply_profile_scale(p, 1.0)
        assert scaled.value == pytest.approx(30.0)
