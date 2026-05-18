"""
parametric-fan-cfd
==================
Parametric fan blade generator and OpenFOAM CFD optimization pipeline.

Modules
-------
config          Pydantic config models and YAML loader
geometry        3D blade and assembly geometry generation
openfoam        OpenFOAM case builder, runner, and postprocessor
multistage      Multi-stage assembly helpers and validation
optimization    Objective functions and optimizer implementations
utils           Logging, path helpers
"""

__version__ = "0.1.0"
__all__ = ["config", "geometry", "openfoam", "multistage", "optimization", "utils"]
