#!/usr/bin/env python3
"""
optimize.py
===========
Run the optimization loop to find high-performance fan designs.

Usage
-----
    python scripts/optimize.py --config configs/example_single_stage_rotor.yaml --n-trials 20
    python scripts/optimize.py --config configs/example_rotor_stator.yaml --method differential_evolution --n-trials 50
    python scripts/optimize.py --config configs/example_multistage_axial.yaml --n-trials 10 --output-dir runs/opt_run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fan_cfd.config import load_config
from fan_cfd.optimization.optimizer import (
    BayesianOptimizer,
    DifferentialEvolutionOptimizer,
    GeneticAlgorithmOptimizer,
    RandomSearchOptimizer,
)
from fan_cfd.utils.logging_utils import get_logger

logger = get_logger("fan-optimize")

OPTIMIZERS = {
    "random": RandomSearchOptimizer,
    "differential_evolution": DifferentialEvolutionOptimizer,
    "bayesian": BayesianOptimizer,
    "genetic": GeneticAlgorithmOptimizer,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run optimization loop for fan design.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file.")
    parser.add_argument(
        "--n-trials", "-n",
        type=int, default=20,
        help="Number of optimization trials. Default: 20.",
    )
    parser.add_argument(
        "--method", "-m",
        choices=list(OPTIMIZERS.keys()),
        default="random",
        help="Optimization method. Default: random.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for trial results. Defaults to runs/<fan_name>/optimization/.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config_path = Path(args.config)
    logger.info("Loading config: %s", config_path)
    try:
        config = load_config(config_path)
    except Exception as exc:
        logger.error("Config load failed: %s", exc)
        return 1

    fan = config.fan
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("runs") / fan.name / "optimization"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting %s optimization: %d trials → %s",
        args.method, args.n_trials, output_dir
    )

    OptimizerClass = OPTIMIZERS[args.method]
    optimizer = OptimizerClass(
        base_config=config,
        n_trials=args.n_trials,
        output_dir=output_dir,
    )

    try:
        result = optimizer.run()
    except KeyboardInterrupt:
        logger.warning("Optimization interrupted by user.")
        return 1
    except Exception as exc:
        logger.error("Optimization failed: %s", exc)
        import traceback
        traceback.print_exc()
        return 1

    if result.best_trial and result.best_trial.valid:
        perf = result.best_trial.performance
        logger.info("=== Best design (trial %d) ===", result.best_trial.trial_id)
        logger.info("  Score:         %.4f", result.best_trial.score)
        logger.info("  Efficiency:    %.2f %%", perf.efficiency * 100 if perf else float("nan"))
        logger.info("  Pressure rise: %.1f Pa", perf.pressure_rise_pa if perf else float("nan"))
        logger.info("  Flow rate:     %.4f m³/s", perf.flow_rate_m3_s if perf else float("nan"))
        logger.info("  Design vars:   %s", result.best_trial.design_variables)
    else:
        logger.warning("No valid trials completed.")

    logger.info("Leaderboard: %s", output_dir / "leaderboard.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
