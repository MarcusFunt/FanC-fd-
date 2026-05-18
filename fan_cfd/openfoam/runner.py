"""
fan_cfd.openfoam.runner
========================
Subprocess wrappers for running OpenFOAM commands and detecting errors.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fan_cfd.utils.logging_utils import get_logger

if TYPE_CHECKING:
    from fan_cfd.config import CFDConfig

logger = get_logger(__name__)

# Patterns that indicate solver divergence
_DIVERGENCE_PATTERNS = [
    r"FOAM FATAL (?:IO )?ERROR",
    r"FOAM exiting",
    r"^Floating point exception",
    r"\bnan\b",
    r"Too many iterations",
    r"Divergence detected",
]

_DIVERGENCE_RE = re.compile("|".join(_DIVERGENCE_PATTERNS), re.IGNORECASE | re.MULTILINE)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class CheckMeshResult:
    """Results from checkMesh."""

    passed: bool = False
    max_non_ortho: float = float("nan")
    max_skewness: float = float("nan")
    n_cells: int = 0
    n_faces: int = 0
    warnings: list[str] = field(default_factory=list)
    log_text: str = ""


@dataclass
class SolverResult:
    """Results from simpleFoam run."""

    converged: bool = False
    diverged: bool = False
    n_iterations: int = 0
    final_residuals: dict[str, float] = field(default_factory=dict)
    log_text: str = ""
    wall_time_s: float = 0.0


@dataclass
class RunResult:
    """Combined result of the full pipeline."""

    success: bool = False
    check_mesh: CheckMeshResult = field(default_factory=CheckMeshResult)
    solver: SolverResult = field(default_factory=SolverResult)
    error_message: str = ""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class OpenFoamRunner:
    """
    Runs OpenFOAM commands in a case directory.

    Each command is logged to ``<case_dir>/log.<command>``.

    Parameters
    ----------
    case_dir : Path
        Path to the OpenFOAM case directory.
    config : CFDConfig
        CFD configuration (for run settings).
    """

    def __init__(self, case_dir: Path, config: "CFDConfig") -> None:
        self.case_dir = Path(case_dir)
        self.config = config
        self.log_dir = self.case_dir  # logs go directly in the case dir

    # ------------------------------------------------------------------
    # Public pipeline
    # ------------------------------------------------------------------

    def run_full_pipeline(self) -> RunResult:
        """
        Execute the full mesh + solve pipeline.

        Steps:
        1. blockMesh
        2. surfaceFeatureExtract
        3. snappyHexMesh
        4. checkMesh
        5. simpleFoam (serial or mpirun)
        """
        result = RunResult()

        # 1. blockMesh
        logger.info("Running blockMesh ...")
        if not self.run_block_mesh():
            result.error_message = "blockMesh failed"
            return result

        # 2. Surface feature extract
        logger.info("Running surfaceFeatureExtract ...")
        self.run_surface_feature_extract()  # non-fatal if missing STLs

        # 3. snappyHexMesh
        logger.info("Running snappyHexMesh ...")
        if not self.run_snappy_hex_mesh():
            result.error_message = "snappyHexMesh failed"
            return result

        # 4. checkMesh
        if (self.case_dir / "system" / "topoSetDict").exists():
            logger.info("Running topoSet ...")
            rc, _ = self.run_command(["topoSet"], "topoSet")
            if rc != 0:
                result.error_message = "topoSet failed"
                return result

        # 5. checkMesh
        logger.info("Running checkMesh ...")
        result.check_mesh = self.run_check_mesh()
        if not result.check_mesh.passed:
            logger.warning("checkMesh reported issues but continuing")

        # 6. Decompose if parallel
        if self.config.run.parallel:
            logger.info("Running decomposePar ...")
            rc, _ = self.run_command(["decomposePar"], "decomposePar")
            if rc != 0:
                result.error_message = "decomposePar failed"
                return result

        # 7. Solver
        logger.info("Running %s ...", self.config.solver)
        result.solver = self.run_solver()
        result.success = not result.solver.diverged

        return result

    def run_block_mesh(self) -> bool:
        rc, log = self.run_command(["blockMesh"], "blockMesh")
        return rc == 0

    def run_surface_feature_extract(self) -> bool:
        rc, log = self.run_command(["surfaceFeatureExtract"], "surfaceFeatureExtract")
        return rc == 0

    def run_snappy_hex_mesh(self) -> bool:
        cmd = ["snappyHexMesh", "-overwrite"]
        if self.config.run.parallel:
            cmd = ["mpirun", "-np", str(self.config.run.n_procs)] + cmd + ["-parallel"]
        rc, log = self.run_command(cmd, "snappyHexMesh")
        return rc == 0

    def run_check_mesh(self) -> CheckMeshResult:
        rc, log = self.run_command(["checkMesh"], "checkMesh")
        return _parse_check_mesh_log(log)

    def run_solver(self) -> SolverResult:
        t0 = time.time()
        cmd: list[str]
        if self.config.run.parallel:
            cmd = [
                "mpirun", "-np", str(self.config.run.n_procs),
                self.config.solver, "-parallel",
            ]
        else:
            cmd = [self.config.solver]
        rc, log = self.run_command(cmd, self.config.solver)
        elapsed = time.time() - t0
        return _parse_solver_log(log, elapsed)

    # ------------------------------------------------------------------
    # Core subprocess wrapper
    # ------------------------------------------------------------------

    def run_command(self, cmd: list[str], log_name: str) -> tuple[int, str]:
        """
        Run an OpenFOAM command in the case directory.

        Streams stdout/stderr to:
        - Python logger (at DEBUG level)
        - A log file at ``<case_dir>/log.<log_name>``

        Returns
        -------
        (return_code, full_output_text)
        """
        log_file = self.log_dir / f"log.{log_name}"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.debug("CMD: %s", " ".join(cmd))

        collected: list[str] = []
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.case_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            with open(log_file, "w") as lf:
                for line in proc.stdout:  # type: ignore[union-attr]
                    line_stripped = line.rstrip("\n")
                    collected.append(line_stripped)
                    lf.write(line)
                    lf.flush()
                    logger.debug("[%s] %s", log_name, line_stripped)

            proc.wait()
            full_text = "\n".join(collected)
            if proc.returncode != 0:
                logger.warning("%s exited with code %d", cmd[0], proc.returncode)
            return proc.returncode, full_text

        except FileNotFoundError:
            msg = (
                f"Command not found: {cmd[0]}. "
                "Is OpenFOAM installed and sourced? (source /opt/openfoam*/etc/bashrc)"
            )
            logger.error(msg)
            log_file.write_text(msg)
            return 127, msg
        except Exception as exc:
            logger.error("Unexpected error running %s: %s", cmd[0], exc)
            return 1, str(exc)


# ---------------------------------------------------------------------------
# Log parsers
# ---------------------------------------------------------------------------


def _parse_check_mesh_log(log: str) -> CheckMeshResult:
    """Extract key metrics from a checkMesh log."""
    result = CheckMeshResult()
    result.log_text = log

    # Check for overall pass
    if "Mesh OK" in log or "No errors found" in log:
        result.passed = True
    elif "FAILED" in log or "failed" in log:
        result.passed = False
    else:
        result.passed = True  # optimistic default

    # Number of cells
    m = re.search(r"cells:\s+(\d+)", log)
    if m:
        result.n_cells = int(m.group(1))

    m = re.search(r"faces:\s+(\d+)", log)
    if m:
        result.n_faces = int(m.group(1))

    # Non-orthogonality
    m = re.search(
        r"(?:Max non-orthogonality\s*=\s*|Mesh non-orthogonality\s+Max:\s*)"
        r"([\d.eE+\-]+)",
        log,
    )
    if m:
        result.max_non_ortho = float(m.group(1))

    # Skewness
    m = re.search(r"Max skewness\s*=\s*([\d.eE+\-]+)", log)
    if m:
        result.max_skewness = float(m.group(1))

    # Extract warnings
    for line in log.splitlines():
        if "***" in line or "Warning" in line or "FATAL" in line:
            result.warnings.append(line.strip())

    return result


def _parse_solver_log(log: str, elapsed: float) -> SolverResult:
    """Extract convergence data from a simpleFoam log."""
    result = SolverResult()
    result.log_text = log
    result.wall_time_s = elapsed

    # Check divergence
    if _DIVERGENCE_RE.search(log):
        result.diverged = True
        return result

    # Count iterations
    iter_matches = re.findall(r"^Time = ([\d.]+)s?", log, re.MULTILINE)
    if iter_matches:
        result.n_iterations = int(float(iter_matches[-1]))

    # Final residuals
    # OpenFOAM prints: "Solving for U, Initial residual = X, Final residual = Y, ..."
    for field_name in ("Ux", "Uy", "Uz", "p", "k", "omega"):
        pattern = rf"Solving for {field_name},.*?Final residual = ([\d.eE+\-]+)"
        matches = re.findall(pattern, log)
        if matches:
            result.final_residuals[field_name] = float(matches[-1])

    # Check convergence by residual targets
    max_res = max(result.final_residuals.values(), default=1.0)
    result.converged = max_res < 1e-3

    return result
