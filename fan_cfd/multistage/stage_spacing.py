"""
fan_cfd.multistage.stage_spacing
==================================
Utilities for computing and suggesting axial stage positions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fan_cfd.config import FanConfig, StageConfig


def compute_axial_clearances(stages: "list[StageConfig]") -> list[float]:
    """
    Return the axial gap (m) between each pair of consecutive stages.

    Returns a list of length ``len(stages) - 1``.
    """
    sorted_stages = sorted(stages, key=lambda s: s.axial_position_m)
    gaps: list[float] = []
    for i in range(len(sorted_stages) - 1):
        gap = sorted_stages[i + 1].axial_position_m - sorted_stages[i].axial_position_m
        gaps.append(gap)
    return gaps


def suggest_stage_positions(
    fan: "FanConfig",
    n_stages: int,
    spacing_m: float,
    start_offset_m: float = 0.01,
) -> list[float]:
    """
    Auto-compute evenly spaced axial positions for *n_stages* stages.

    Parameters
    ----------
    fan : FanConfig
        Used for duct bounds if available.
    n_stages : int
        Number of stages to position.
    spacing_m : float
        Axial distance between consecutive stage positions (m).
    start_offset_m : float
        Offset from the duct inlet (or 0) for the first stage.

    Returns
    -------
    list[float]
        Axial positions in metres, length == n_stages.
    """
    positions: list[float] = []
    z = start_offset_m
    for _ in range(n_stages):
        positions.append(round(z, 6))
        z += spacing_m
    return positions


def auto_space_stages(
    stages: "list[StageConfig]",
    total_length_m: float,
    margin_m: float = 0.01,
) -> list[float]:
    """
    Redistribute stages evenly within a total axial length.

    Parameters
    ----------
    stages : list[StageConfig]
    total_length_m : float
        Total available axial length (e.g. duct length minus clearances).
    margin_m : float
        Margin to leave at each end.

    Returns
    -------
    list[float]
        New axial positions (same order as input stages).
    """
    n = len(stages)
    if n == 0:
        return []
    if n == 1:
        return [total_length_m / 2.0]

    usable = total_length_m - 2 * margin_m
    spacing = usable / (n - 1)
    return [margin_m + i * spacing for i in range(n)]
