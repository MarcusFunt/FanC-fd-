"""
fan_cfd.utils.names
===================
Identifier normalization helpers for external solver artifacts.
"""

from __future__ import annotations

import re

_INVALID_OPENFOAM_CHARS_RE = re.compile(r"[^A-Za-z0-9_]+")
_REPEATED_UNDERSCORES_RE = re.compile(r"_+")


def openfoam_identifier(name: str, fallback: str = "stage") -> str:
    """
    Convert a user-facing name into a stable OpenFOAM dictionary/STL identifier.

    OpenFOAM patch, zone, and function-object names are safest when limited to
    word characters and when they do not begin with a digit.
    """
    identifier = _INVALID_OPENFOAM_CHARS_RE.sub("_", str(name).strip())
    identifier = _REPEATED_UNDERSCORES_RE.sub("_", identifier).strip("_")
    fallback = _INVALID_OPENFOAM_CHARS_RE.sub("_", fallback.strip()) or "stage"

    if not identifier:
        return fallback
    if identifier[0].isdigit():
        return f"{fallback}_{identifier}"
    return identifier
