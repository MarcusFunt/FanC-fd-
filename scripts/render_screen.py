#!/usr/bin/env python3
"""
render_screen.py
================
Generate an HTML screen showing the full fan assembly and CFD results.

Usage
-----
    python scripts/render_screen.py --run-dir runs/openfoam_smoke_test
    python scripts/render_screen.py --run-dir runs/my_run --output runs/my_run/render.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fan_cfd.rendering import write_render_screen
from fan_cfd.utils.logging_utils import get_logger

logger = get_logger("fan-render")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML render screen for a FanCFD run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--run-dir",
        "-r",
        required=True,
        help="Run directory containing geometry/full_assembly.stl and results/results.json.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output HTML path. Defaults to <run-dir>/render/index.html.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional page title.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = write_render_screen(
            run_dir=Path(args.run_dir),
            output_path=Path(args.output) if args.output else None,
            title=args.title,
        )
    except Exception as exc:
        logger.error("Render screen generation failed: %s", exc)
        return 1

    logger.info("Render screen written: %s", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
