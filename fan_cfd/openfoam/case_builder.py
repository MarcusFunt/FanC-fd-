"""
fan_cfd.openfoam.case_builder
==============================
Assembles a complete OpenFOAM case directory from config and STL geometry.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from fan_cfd.openfoam.dict_writer import (
    write_block_mesh_dict,
    write_boundary_condition_U,
    write_boundary_condition_k,
    write_boundary_condition_nut,
    write_boundary_condition_omega,
    write_boundary_condition_p,
    write_control_dict,
    write_decompose_par_dict,
    write_function_objects,
    write_fv_schemes,
    write_fv_solution,
    write_snappy_hex_mesh_dict,
    write_transport_properties,
    write_turbulence_properties,
)
from fan_cfd.openfoam.cell_zones import write_topo_set_dict
from fan_cfd.openfoam.mrf_zones import build_mrf_zones, write_mrf_properties
from fan_cfd.utils.logging_utils import get_logger
from fan_cfd.utils.paths import get_template_dir

if TYPE_CHECKING:
    from fan_cfd.config import FanCFDConfig

logger = get_logger(__name__)


class OpenFoamCaseBuilder:
    """
    Builds a complete OpenFOAM simpleFoam + MRF case directory.

    Parameters
    ----------
    config : FanCFDConfig
        Full validated configuration.
    case_dir : Path
        Target directory for the OpenFOAM case.
    """

    def __init__(self, config: "FanCFDConfig", case_dir: Path) -> None:
        self.config = config
        self.case_dir = Path(case_dir)
        self.fan = config.fan
        self.cfd = config.cfd
        self._stl_paths: dict[str, Path] = {}
        self._mrf_zones = build_mrf_zones(self.fan)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build(self, stl_paths: dict[str, Path] | None = None) -> None:
        """
        Full pipeline: copy template, place STLs, write all dict files.

        Parameters
        ----------
        stl_paths : dict[str, Path], optional
            If provided, STL files are copied into the case triSurface dir.
        """
        logger.info("Building OpenFOAM case at %s", self.case_dir)
        self.copy_template()
        if stl_paths:
            self.place_stl_files(stl_paths)
        self.write_block_mesh_dict()
        self.write_snappy_hex_mesh_dict()
        self.write_mrf_properties()
        self.write_topo_set_dict()
        self.write_transport_properties()
        self.write_turbulence_properties()
        self.write_boundary_conditions()
        self.write_control_dict()
        self.write_fv_schemes()
        self.write_fv_solution()
        self.write_function_objects()
        if self.cfd.run.parallel:
            self.write_decompose_par_dict()
        logger.info("Case build complete.")

    def copy_template(self) -> None:
        """Copy the base template directory into case_dir."""
        template = get_template_dir()
        if template.exists():
            logger.debug("Copying template from %s", template)
            if self.case_dir.exists():
                shutil.rmtree(self.case_dir)
            shutil.copytree(str(template), str(self.case_dir))
        else:
            logger.warning("Template not found at %s; creating directory structure", template)
            for sub in ["0", "constant", "system", "constant/triSurface"]:
                (self.case_dir / sub).mkdir(parents=True, exist_ok=True)

    def place_stl_files(self, stl_paths: dict[str, Path]) -> None:
        """Copy STL files into constant/triSurface/."""
        tri_dir = self.case_dir / "constant" / "triSurface"
        tri_dir.mkdir(parents=True, exist_ok=True)
        self._stl_paths = {}
        for name, src in stl_paths.items():
            dst = tri_dir / src.name
            shutil.copy2(str(src), str(dst))
            self._stl_paths[name] = dst
            logger.debug("Placed %s → %s", src.name, dst)

    # ------------------------------------------------------------------
    # Dict writers
    # ------------------------------------------------------------------

    def write_block_mesh_dict(self) -> None:
        content = write_block_mesh_dict(self.cfd, self.fan)
        self._write("system/blockMeshDict", content)

    def write_snappy_hex_mesh_dict(self) -> None:
        stl_names = [p.name for p in self._stl_paths.values()]
        content = write_snappy_hex_mesh_dict(self.cfd, self.fan, stl_names)
        self._write("system/snappyHexMeshDict", content)

    def write_mrf_properties(self) -> None:
        out = self.case_dir / "constant" / "MRFProperties"
        write_mrf_properties(self._mrf_zones, out)
        logger.debug("Wrote MRFProperties with %d zones", len(self._mrf_zones))

    def write_topo_set_dict(self) -> None:
        if not self._mrf_zones:
            return
        out = self.case_dir / "system" / "topoSetDict"
        write_topo_set_dict(self._mrf_zones, self.fan, out)
        logger.debug("Wrote topoSetDict with %d zones", len(self._mrf_zones))

    def write_transport_properties(self) -> None:
        content = write_transport_properties(self.cfd.fluid)
        self._write("constant/transportProperties", content)

    def write_turbulence_properties(self) -> None:
        content = write_turbulence_properties(self.cfd.turbulence_model)
        self._write("constant/turbulenceProperties", content)

    def write_boundary_conditions(self) -> None:
        bc_dir = self.case_dir / "0"
        bc_dir.mkdir(parents=True, exist_ok=True)
        (bc_dir / "U").write_text(write_boundary_condition_U(self.cfd))
        (bc_dir / "p").write_text(write_boundary_condition_p(self.cfd))
        (bc_dir / "k").write_text(write_boundary_condition_k(self.cfd))
        (bc_dir / "omega").write_text(write_boundary_condition_omega(self.cfd))
        (bc_dir / "nut").write_text(write_boundary_condition_nut(self.cfd))
        logger.debug("Wrote boundary conditions to 0/")

    def write_control_dict(self) -> None:
        content = write_control_dict(self.cfd)
        self._write("system/controlDict", content)

    def write_fv_schemes(self) -> None:
        self._write("system/fvSchemes", write_fv_schemes())

    def write_fv_solution(self) -> None:
        self._write("system/fvSolution", write_fv_solution())

    def write_function_objects(self) -> None:
        content = write_function_objects(self.fan)
        self._write("system/functionObjects", content)

    def write_decompose_par_dict(self) -> None:
        n = self.cfd.run.n_procs
        content = write_decompose_par_dict(n)
        self._write("system/decomposeParDict", content)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, rel_path: str, content: str) -> None:
        full = self.case_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        logger.debug("Wrote %s", rel_path)
