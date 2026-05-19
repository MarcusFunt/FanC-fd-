#!/usr/bin/env python3
"""
Build and run the FanCFD OpenFOAM Docker environment.

Default behavior:
  1. Build the local Docker image.
  2. Run the Python test suite inside the image.
  3. Generate the default 50 mm three-stack geometry.
  4. Build the OpenFOAM case and render the viewer without running CFD.

Use --full-cfd to run the complete mesh + solve pipeline.
Use --command to run an arbitrary command inside the prepared container.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path


DEFAULT_IMAGE = "fan-cfd-openfoam:local"
DEFAULT_CONFIG = "configs/fifty_mm_three_stack_tmp_120w.yaml"
DEFAULT_RUN_DIR = "runs/docker_fifty_mm_three_stack_tmp_120w"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and run the Dockerized FanCFD pipeline.")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"Docker image tag. Default: {DEFAULT_IMAGE}")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Fan config to run. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR, help=f"Run output directory. Default: {DEFAULT_RUN_DIR}")
    parser.add_argument("--skip-build", action="store_true", help="Reuse an existing Docker image.")
    parser.add_argument("--build-only", action="store_true", help="Only build the Docker image.")
    parser.add_argument("--full-cfd", action="store_true", help="Run OpenFOAM mesh and solver instead of case-build smoke validation.")
    parser.add_argument("--no-user-map", action="store_true", help="Do not map the current Unix UID/GID into the container.")
    parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="Run an arbitrary command in the container after optional image build.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    if not args.skip_build:
        run(["docker", "build", "-t", args.image, "."], cwd=repo_root)

    if args.build_only:
        return 0

    if args.command:
        docker_run(args, repo_root, args.command)
        return 0

    config = container_workspace_path(args.config, repo_root)
    run_dir = container_workspace_path(args.run_dir, repo_root)

    commands = [
        "python -m pytest -q",
        f"python scripts/generate_geometry.py --config {q(config)} --output-dir {q(run_dir + '/geometry')}",
    ]

    case_cmd = f"python scripts/run_case.py --config {q(config)} --output-dir {q(run_dir)}"
    if not args.full_cfd:
        case_cmd += " --skip-geometry --skip-solve"
    commands.append(case_cmd)

    docker_run(args, repo_root, ["bash", "-lc", " && ".join(commands)])
    return 0


def run(cmd: list[str], cwd: Path) -> None:
    print("+ " + shlex.join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def docker_run(args: argparse.Namespace, repo_root: Path, command: list[str]) -> None:
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{repo_root}:/workspace",
        "-w",
        "/workspace",
        "-e",
        "PYTHONPATH=/workspace",
    ]

    if os.name != "nt" and not args.no_user_map:
        docker_cmd += ["--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp"]

    docker_cmd += [args.image] + command
    run(docker_cmd, cwd=repo_root)


def container_workspace_path(path_value: str, repo_root: Path) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        return Path(path_value).as_posix()

    resolved = path.resolve()
    try:
        rel = resolved.relative_to(repo_root)
    except ValueError as exc:
        raise SystemExit(f"Path must be inside the repository: {resolved}") from exc
    return f"/workspace/{rel.as_posix()}"


def q(value: str) -> str:
    return shlex.quote(value)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
