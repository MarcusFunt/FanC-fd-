"""
fan_cfd.config
==============
Pydantic v2 configuration models for parametric-fan-cfd.

All physical quantities are in SI units unless noted.

Backward-compatibility shim: configs using the old-style top-level
``rotor_only`` / ``rotor_stator`` / single ``blade:`` block are
automatically converted to the canonical ``stages`` list format.
"""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProfileType(str, Enum):
    CONTROL_POINTS = "control_points"
    CONSTANT = "constant"
    LINEAR = "linear"
    INHERIT = "inherit"


class StageType(str, Enum):
    ROTOR = "rotor"
    STATOR = "stator"


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------


class Profile(BaseModel):
    """Radial distribution profile for chord, twist, rake, or skew."""

    type: ProfileType = ProfileType.CONSTANT
    points: list[tuple[float, float]] | None = None  # [(r_norm, value), ...]
    value: float | None = None
    from_stage: str | None = None  # for INHERIT
    scale: float = 1.0  # scaling factor for inherited profile

    @model_validator(mode="after")
    def _check_consistency(self) -> "Profile":
        if self.type == ProfileType.CONTROL_POINTS:
            if not self.points or len(self.points) < 2:
                raise ValueError("control_points profile requires at least 2 points")
        if self.type == ProfileType.CONSTANT:
            if self.value is None:
                raise ValueError("constant profile requires 'value'")
        if self.type == ProfileType.LINEAR:
            if not self.points or len(self.points) != 2:
                raise ValueError(
                    "linear profile requires exactly 2 points: [(r0, v0), (r1, v1)]"
                )
        if self.type == ProfileType.INHERIT:
            if not self.from_stage:
                raise ValueError("inherit profile requires 'from_stage'")
        return self

    @classmethod
    def constant(cls, value: float) -> "Profile":
        return cls(type=ProfileType.CONSTANT, value=value)

    @classmethod
    def linear(cls, v0: float, v1: float) -> "Profile":
        return cls(type=ProfileType.LINEAR, points=[(0.0, v0), (1.0, v1)])

    @classmethod
    def control_points(cls, pts: list[tuple[float, float]]) -> "Profile":
        return cls(type=ProfileType.CONTROL_POINTS, points=pts)


# ---------------------------------------------------------------------------
# Blade config
# ---------------------------------------------------------------------------


class BladeConfig(BaseModel):
    """Geometry definition for one set of blades (all blades in a stage share this)."""

    airfoil: str = "naca4412"
    radial_sections: int = Field(default=9, ge=3, le=50)
    chord_profile: Profile = Field(default_factory=lambda: Profile.constant(0.03))
    twist_profile_deg: Profile = Field(default_factory=lambda: Profile.constant(30.0))
    thickness_scale: float = Field(default=1.0, gt=0.0, le=5.0)
    rake_profile: Profile | None = None
    skew_profile: Profile | None = None

    @field_validator("airfoil")
    @classmethod
    def _validate_airfoil(cls, v: str) -> str:
        v = v.lower().strip()
        if v.startswith("naca") and len(v) == 8 and v[4:].isdigit():
            return v
        if v.startswith("naca") and len(v) == 7 and v[4:].isdigit():
            return v
        # Accept any string for extensibility; warn but don't reject
        return v


# ---------------------------------------------------------------------------
# Stage config
# ---------------------------------------------------------------------------


class StageConfig(BaseModel):
    """Configuration for one rotor or stator stage."""

    name: str
    type: StageType
    axial_position_m: float = Field(ge=0.0)
    blade_count: int = Field(ge=2, le=200)
    blade: BladeConfig = Field(default_factory=BladeConfig)
    rpm: float | None = Field(default=None, ge=0.0)
    rotation_direction: Literal["clockwise", "counterclockwise"] | None = None

    @model_validator(mode="after")
    def _rotor_needs_rpm_or_inherits(self) -> "StageConfig":
        # RPM can come from fan-level default; we don't enforce here
        return self

    @property
    def omega_rad_s(self) -> float:
        """Angular velocity in rad/s (requires rpm to be set)."""
        if self.rpm is None:
            raise ValueError(f"Stage '{self.name}' has no RPM defined")
        return self.rpm * 2.0 * math.pi / 60.0

    @property
    def rotation_sign(self) -> float:
        """+1 for counterclockwise (default), -1 for clockwise (viewed from inlet)."""
        if self.rotation_direction == "clockwise":
            return -1.0
        return 1.0


# ---------------------------------------------------------------------------
# Duct config
# ---------------------------------------------------------------------------


class DuctConfig(BaseModel):
    """Annular duct surrounding the fan assembly."""

    enabled: bool = True
    inner_diameter_m: float = Field(gt=0.0)
    wall_thickness_m: float = Field(default=0.003, gt=0.0)
    total_length_m: float = Field(gt=0.0)
    inlet_clearance_m: float = Field(default=0.01, ge=0.0)
    outlet_clearance_m: float = Field(default=0.01, ge=0.0)

    @property
    def outer_diameter_m(self) -> float:
        return self.inner_diameter_m + 2.0 * self.wall_thickness_m

    @property
    def inner_radius_m(self) -> float:
        return self.inner_diameter_m / 2.0


# ---------------------------------------------------------------------------
# Hub config
# ---------------------------------------------------------------------------


class HubConfig(BaseModel):
    """Central hub geometry."""

    diameter_m: float = Field(gt=0.0)
    length_m: float | None = None  # auto-computed from stages if None

    @property
    def radius_m(self) -> float:
        return self.diameter_m / 2.0


# ---------------------------------------------------------------------------
# Fan config
# ---------------------------------------------------------------------------


class FanConfig(BaseModel):
    """Top-level fan geometry configuration."""

    name: str = "fan"
    max_diameter_m: float = Field(gt=0.0)
    hub_diameter_m: float = Field(gt=0.0)
    rpm: float = Field(gt=0.0)  # global default RPM
    duct: DuctConfig | None = None
    stages: list[StageConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _propagate_rpm_and_validate(self) -> "FanConfig":
        # Propagate global RPM to rotor stages that don't have their own
        for stage in self.stages:
            if stage.type == StageType.ROTOR and stage.rpm is None:
                object.__setattr__(stage, "rpm", self.rpm)
        # Hub must be smaller than max diameter
        if self.hub_diameter_m >= self.max_diameter_m:
            raise ValueError("hub_diameter_m must be less than max_diameter_m")
        return self

    @property
    def tip_radius_m(self) -> float:
        return self.max_diameter_m / 2.0

    @property
    def hub_radius_m(self) -> float:
        return self.hub_diameter_m / 2.0

    @property
    def rotor_stages(self) -> list[StageConfig]:
        return [s for s in self.stages if s.type == StageType.ROTOR]

    @property
    def stator_stages(self) -> list[StageConfig]:
        return [s for s in self.stages if s.type == StageType.STATOR]


# ---------------------------------------------------------------------------
# CFD sub-configs
# ---------------------------------------------------------------------------


class BoundaryConfig(BaseModel):
    """CFD boundary condition at one patch."""

    patch_name: str = "inlet"
    velocity_m_s: float = Field(default=5.0, gt=0.0)
    turbulence_intensity: float = Field(default=0.05, gt=0.0, le=1.0)
    hydraulic_diameter_m: float = Field(default=0.12, gt=0.0)


class FluidConfig(BaseModel):
    """Fluid properties."""

    nu_m2_s: float = Field(default=1.5e-5, gt=0.0)  # kinematic viscosity (air at 20°C)
    rho_kg_m3: float = Field(default=1.225, gt=0.0)  # density


class MeshConfig(BaseModel):
    """Mesh generation settings."""

    base_cell_size_m: float = Field(default=0.005, gt=0.0)
    refinement_levels: int = Field(default=3, ge=1, le=6)
    boundary_layers: int = Field(default=5, ge=0, le=10)
    boundary_layer_expansion: float = Field(default=1.2, gt=1.0)
    domain_length_factor: float = Field(default=5.0, gt=1.0)
    n_processors: int = Field(default=4, ge=1)


class RunConfig(BaseModel):
    """Solver run settings."""

    n_iterations: int = Field(default=1000, ge=10)
    write_interval: int = Field(default=100, ge=1)
    convergence_residual: float = Field(default=1e-4, gt=0.0)
    parallel: bool = False
    n_procs: int = Field(default=4, ge=1)
    purge_write: int = Field(default=1, ge=0)


class CFDConfig(BaseModel):
    """Full CFD run configuration."""

    solver: str = "simpleFoam"
    rotation_model: str = "MRF"
    turbulence_model: str = "kOmegaSST"
    inlet: BoundaryConfig = Field(default_factory=BoundaryConfig)
    outlet: BoundaryConfig = Field(
        default_factory=lambda: BoundaryConfig(patch_name="outlet", velocity_m_s=5.0)
    )
    fluid: FluidConfig = Field(default_factory=FluidConfig)
    mesh: MeshConfig = Field(default_factory=MeshConfig)
    run: RunConfig = Field(default_factory=RunConfig)


# ---------------------------------------------------------------------------
# Objective config
# ---------------------------------------------------------------------------


class ObjectiveConfig(BaseModel):
    """Optimization objective specification."""

    mode: Literal["single", "multi_objective"] = "single"
    maximize: str = "efficiency"  # "efficiency" | "pressure_rise" | "flow_rate"
    constraints: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)  # for multi_objective


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class FanCFDConfig(BaseModel):
    """Root configuration model."""

    fan: FanConfig
    cfd: CFDConfig = Field(default_factory=CFDConfig)
    objective: ObjectiveConfig = Field(default_factory=ObjectiveConfig)


# ---------------------------------------------------------------------------
# Backward-compatibility conversion
# ---------------------------------------------------------------------------


def _convert_legacy_config(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convert old-style (pre-stages) config dicts to the canonical stages format.

    Old formats supported:
    - Top-level ``blade:`` block with ``fan.rpm`` / ``fan.blade_count``
    - ``fan.rotor_only: true`` flag
    - ``fan.rotor_stator: {stator_blade_count, stator_axial_position_m}``

    Returns a new dict in canonical format (mutated copy).
    """
    raw = dict(raw)  # shallow copy
    fan = dict(raw.get("fan", {}))

    if "stages" in fan:
        raw["fan"] = fan
        return raw  # already canonical

    # Build stages list from old-style keys
    stages: list[dict] = []

    blade_raw = fan.pop("blade", {})
    blade_count = fan.pop("blade_count", 5)
    axial_pos = fan.pop("axial_position_m", 0.0)

    # Rotor stage
    rotor: dict[str, Any] = {
        "name": "rotor_1",
        "type": "rotor",
        "axial_position_m": axial_pos,
        "blade_count": blade_count,
        "blade": blade_raw,
    }
    stages.append(rotor)

    # Optional stator
    rs = fan.pop("rotor_stator", None)
    if rs:
        rs = dict(rs)
        stator: dict[str, Any] = {
            "name": "stator_1",
            "type": "stator",
            "axial_position_m": rs.get("stator_axial_position_m", axial_pos + 0.04),
            "blade_count": rs.get("stator_blade_count", blade_count + 2),
            "blade": blade_raw,
        }
        stages.append(stator)

    fan.pop("rotor_only", None)  # discard legacy flag
    fan["stages"] = stages
    raw["fan"] = fan
    return raw


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> FanCFDConfig:
    """
    Load and validate a FanCFDConfig from a YAML file.

    Automatically converts legacy (pre-stages) config formats.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if raw is None:
        raise ValueError(f"Config file is empty: {path}")

    raw = _convert_legacy_config(raw)
    return FanCFDConfig.model_validate(raw)
