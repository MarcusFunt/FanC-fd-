#!/usr/bin/env python3
"""
generate_geometry.py
====================
Generate fan geometry STL files from a YAML config.

Usage
-----
    python scripts/generate_geometry.py --config configs/example_single_stage_rotor.yaml
    python scripts/generate_geometry.py --config configs/example_multistage_axial.yaml --output-dir runs/my_fan/geometry
    python scripts/generate_geometry.py --config configs/example_rotor_stator.yaml --validate-only
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fan_cfd.config import load_config
from fan_cfd.geometry.cad_export import validate_stl_files
from fan_cfd.geometry.fan_geometry import build_and_export_geometry
from fan_cfd.multistage.stage_config import detect_assembly_mode, resolve_inherited_profiles
from fan_cfd.multistage.stage_validation import validate_stage_sequence
from fan_cfd.utils.logging_utils import get_logger

logger = get_logger("fan-generate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fan blade geometry STL files from a config.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for STL files. Defaults to runs/<fan_name>/geometry/.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the config and geometry without writing files.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    import logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config_path = Path(args.config)
    logger.info("Loading config: %s", config_path)
    try:
        config = load_config(config_path)
    except Exception as exc:
        logger.error("Config load failed: %s", exc)
        return 1

    fan = config.fan
    logger.info("Fan: '%s'  diameter=%.0fmm  %d stages  %.0f RPM",
                fan.name, fan.max_diameter_m * 1000, len(fan.stages), fan.rpm)

    # Resolve inherited profiles
    resolved_stages = resolve_inherited_profiles(fan.stages)
    mode = detect_assembly_mode(resolved_stages)
    logger.info("Assembly mode: %s", mode.value)

    # Validate stage layout
    errors = validate_stage_sequence(resolved_stages, fan, fan.duct)
    if errors:
        for e in errors:
            logger.error("VALIDATION ERROR: %s", e)
        if args.validate_only:
            return 1
        logger.warning("Proceeding despite validation errors...")
    else:
        logger.info("Stage layout validation passed.")

    if args.validate_only:
        logger.info("--validate-only: skipping geometry generation.")
        return 0

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("runs") / fan.name / "geometry"

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", output_dir)

    # Build and export geometry
    try:
        stl_paths = build_and_export_geometry(config, output_dir)
    except Exception as exc:
        logger.error("Geometry generation failed: %s", exc)
        import traceback
        traceback.print_exc()
        return 1

    logger.info("Exported %d STL files:", len(stl_paths))
    for name, path in stl_paths.items():
        size_kb = path.stat().st_size / 1024
        logger.info("  %-30s  %8.1f KB  %s", name, size_kb, path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
