"""
fan_cfd.utils.logging_utils
===========================
Logging configuration for the parametric-fan-cfd package.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with a consistent format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def add_file_handler(logger: logging.Logger, log_path: Path) -> None:
    """Add a file handler to an existing logger."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, mode="a")
    fh.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)


def stream_to_logger(process_stdout, logger: logging.Logger, prefix: str = "") -> str:
    """
    Read lines from a subprocess stdout and forward to a logger.
    Returns the full output as a string.
    """
    lines: list[str] = []
    for raw_line in process_stdout:
        line = raw_line.rstrip("\n")
        lines.append(line)
        logger.debug("%s%s", prefix, line)
    return "\n".join(lines)
