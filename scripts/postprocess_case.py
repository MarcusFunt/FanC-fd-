#!/usr/bin/env python3
"""
postprocess_case.py
===================
Re-run postprocessing on an existing OpenFOAM case directory.

Usage
-----
    python scripts/postprocess_case.py --case runs/my_fan/openfoam --config configs/example_single_stage_rotor.yaml
    python scripts/postprocess_case.py --case /path/to/foam/case --config my_config.yaml --output results/
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fan_cfd.config import load_config
from fan_cfd.openfoam.postprocess import PostProcessor
from fan_cfd.utils.logging_utils import get_logger

logger = get_logger("fan-postprocess")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-run postprocessing on an existing OpenFOAM case.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--case", "-d",
        required=True,
        help="Path to existing OpenFOAM case directory.",
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to YAML config file (used for fan geometry metadata).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path for results JSON output. Defaults to <case>/results.json.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    case_dir = Path(args.case)
    if not case_dir.exists():
        logger.error("Case directory not found: %s", case_dir)
        return 1

    config_path = Path(args.config)
    try:
        config = load_config(config_path)
    except Exception as exc:
        logger.error("Config load failed: %s", exc)
        return 1

    output_path = Path(args.output) if args.output else case_dir / "results.json"

    logger.info("Postprocessing case: %s", case_dir)
    pp = PostProcessor(case_dir, config.fan)

    try:
        perf = pp.extract_all()
    except Exception as exc:
        logger.error("Postprocessing failed: %s", exc)
        import traceback
        traceback.print_exc()
        return 1

    import math
    logger.info("Results:")
    logger.info("  Pressure rise:  %.2f Pa", perf.pressure_rise_pa)
    logger.info("  Flow rate:      %.5f m³/s", perf.flow_rate_m3_s)
    logger.info("  Torque:         %.5f N·m", perf.torque_nm)
    logger.info("  Shaft power:    %.2f W", perf.shaft_power_w)
    eff_pct = perf.efficiency * 100 if not math.isnan(perf.efficiency) else float("nan")
    logger.info("  Efficiency:     %.2f %%", eff_pct)
    logger.info("  Mesh cells:     %d", perf.mesh.n_cells)
    logger.info("  Max non-ortho:  %.1f°", perf.mesh.max_non_ortho)
    logger.info("  Converged:      %s  (%d iterations)", perf.convergence.converged, perf.convergence.n_iterations)

    pp.save_results(perf, output_path)
    logger.info("Results saved: %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
