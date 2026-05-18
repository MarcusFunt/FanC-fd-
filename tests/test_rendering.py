"""
tests/test_rendering.py
=======================
Tests for the HTML render screen generator.
"""

import json
from pathlib import Path

import trimesh

from fan_cfd.rendering import write_render_screen


def test_write_render_screen_creates_html(tmp_path: Path):
    run_dir = tmp_path / "run"
    geometry_dir = run_dir / "geometry"
    results_dir = run_dir / "results"
    geometry_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    mesh = trimesh.creation.box(extents=(0.08, 0.08, 0.02))
    mesh.export(geometry_dir / "full_assembly.stl")
    (results_dir / "results.json").write_text(
        json.dumps(
            {
                "config_name": "render_test",
                "flow_rate_m3_s": 0.125,
                "pressure_rise_pa": 12.5,
                "torque_nm": 0.0042,
                "shaft_power_w": 2.2,
                "efficiency": 0.42,
                "mesh": {
                    "n_cells": 1200,
                    "max_non_ortho": 35.0,
                    "max_skewness": 1.4,
                    "ok": True,
                },
                "convergence": {
                    "converged": True,
                    "n_iterations": 30,
                    "final_residuals": {"Ux": 1e-5, "p": 2e-6},
                },
            }
        ),
        encoding="utf-8",
    )

    output = write_render_screen(run_dir)

    assert output == run_dir / "render" / "index.html"
    html = output.read_text(encoding="utf-8")
    assert "render_test render" in html
    assert "CFD Results" in html
    assert "Full assembly" in html
    assert "<svg" in html
    assert "0.1250 m^3/s" in html
