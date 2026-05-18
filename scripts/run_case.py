#!/usr/bin/env python3
"""
run_case.py
===========
Run the full CFD pipeline: geometry → mesh → solve → postprocess.

Usage
-----
    python scripts/run_case.py --config configs/example_single_stage_rotor.yaml
    python scripts/run_case.py --config configs/example_rotor_stator.yaml --skip-geometry
    python scripts/run_case.py --config configs/example_multistage_axial.yaml --output-dir runs/my_run
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fan_cfd.config import load_config
from fan_cfd.geometry.fan_geometry import build_and_export_geometry
from fan_cfd.multistage.stage_config import resolve_inherited_profiles
from fan_cfd.multistage.stage_validation import validate_stage_sequence
from fan_cfd.openfoam.case_builder import OpenFoamCaseBuilder
from fan_cfd.openfoam.postprocess import PostProcessor
from fan_cfd.openfoam.runner import OpenFoamRunner
from fan_cfd.utils.logging_utils import get_logger

logger = get_logger("fan-run")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full CFD pipeline for a fan config.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file.")
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output base directory. Defaults to runs/<fan_name>/.",
    )
    parser.add_argument("--skip-geometry", action="store_true", help="Skip geometry generation (reuse existing STLs).")
    parser.add_argument("--skip-mesh", action="store_true", help="Skip meshing (run solver on existing mesh).")
    parser.add_argument("--skip-solve", action="store_true", help="Skip solver (only mesh and postprocess).")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    t_start = time.time()

    # Load config
    config_path = Path(args.config)
    logger.info("Loading config: %s", config_path)
    try:
        config = load_config(config_path)
    except Exception as exc:
        logger.error("Config load failed: %s", exc)
        return 1

    fan = config.fan
    logger.info("Fan: '%s'  diameter=%.0fmm  %d stage(s)  %.0f RPM",
                fan.name, fan.max_diameter_m * 1000, len(fan.stages), fan.rpm)

    # Determine output directory
    base_dir = Path(args.output_dir) if args.output_dir else Path("runs") / fan.name
    base_dir.mkdir(parents=True, exist_ok=True)

    geom_dir = base_dir / "geometry"
    case_dir = base_dir / "openfoam"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Validate stages
    resolved_stages = resolve_inherited_profiles(fan.stages)
    errors = validate_stage_sequence(resolved_stages, fan, fan.duct)
    if errors:
        for e in errors:
            logger.warning("Stage validation: %s", e)

    # --- Geometry ---
    stl_paths: dict[str, Path] = {}
    if not args.skip_geometry:
        logger.info("=== Step 1/4: Generating geometry ===")
        try:
            stl_paths = build_and_export_geometry(config, geom_dir)
            logger.info("Generated %d STL files in %s", len(stl_paths), geom_dir)
        except Exception as exc:
            logger.error("Geometry generation failed: %s", exc)
            return 1
    else:
        logger.info("Skipping geometry (--skip-geometry)")
        # Find existing STL files
        if geom_dir.exists():
            stl_paths = {p.stem: p for p in geom_dir.glob("*.stl")}
            logger.info("Found %d existing STL files", len(stl_paths))

    # --- Case build ---
    if not args.skip_mesh:
        logger.info("=== Step 2/4: Building OpenFOAM case ===")
        try:
            builder = OpenFoamCaseBuilder(config, case_dir)
            builder.build(stl_paths)
            logger.info("Case built at %s", case_dir)
        except Exception as exc:
            logger.error("Case build failed: %s", exc)
            return 1

    # --- Solve ---
    run_result = None
    if not args.skip_solve:
        logger.info("=== Step 3/4: Running OpenFOAM ===")
        try:
            runner = OpenFoamRunner(case_dir, config.cfd)
            run_result = runner.run_full_pipeline()
            if run_result.solver.diverged:
                logger.error("Solver diverged! Check logs in %s", case_dir)
            elif run_result.solver.converged:
                logger.info("Solver converged in %d iterations", run_result.solver.n_iterations)
            else:
                logger.warning("Solver finished without confirmed convergence")
        except Exception as exc:
            logger.error("OpenFOAM run failed: %s", exc)
            return 1

    # --- Postprocess ---
    logger.info("=== Step 4/4: Postprocessing ===")
    try:
        pp = PostProcessor(case_dir, fan)
        perf = pp.extract_all()
        pp.save_results(perf, results_dir / "results.json")

        logger.info("Results:")
        logger.info("  Pressure rise:  %.1f Pa", perf.pressure_rise_pa)
        logger.info("  Flow rate:      %.4f m³/s", perf.flow_rate_m3_s)
        logger.info("  Torque:         %.4f N·m", perf.torque_nm)
        logger.info("  Shaft power:    %.1f W", perf.shaft_power_w)
        logger.info("  Efficiency:     %.2f %%", perf.efficiency * 100 if not __import__("math").isnan(perf.efficiency) else float("nan"))
    except Exception as exc:
        logger.error("Postprocessing failed: %s", exc)
        return 1

    elapsed = time.time() - t_start
    logger.info("Total wall time: %.1f s", elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
