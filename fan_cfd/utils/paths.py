"""
fan_cfd.utils.paths
===================
Path resolution helpers for runs, templates, and output directories.
"""

from __future__ import annotations

from pathlib import Path

# Package root (fan_cfd/)
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Project root (one level above fan_cfd/)
PROJECT_ROOT = _PACKAGE_ROOT.parent


def get_template_dir() -> Path:
    """Return the path to the OpenFOAM MRF case template."""
    return PROJECT_ROOT / "templates" / "openfoam_mrf_case"


def get_runs_dir() -> Path:
    """Return the default runs output directory."""
    runs = PROJECT_ROOT / "runs"
    runs.mkdir(exist_ok=True)
    return runs


def make_case_dir(run_name: str, base_dir: Path | None = None) -> Path:
    """Create and return a new case directory under runs/."""
    base = base_dir or get_runs_dir()
    case = base / run_name
    case.mkdir(parents=True, exist_ok=True)
    return case


def make_output_dir(base: Path, sub: str) -> Path:
    """Create and return a sub-directory."""
    d = base / sub
    d.mkdir(parents=True, exist_ok=True)
    return d
