"""
tests/test_api_results.py
=========================
Regression tests for results endpoint path safety.
"""

import pytest
from fastapi import HTTPException

from api.routes import results as results_route


def test_safe_run_dir_rejects_runs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(results_route, "RUNS_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        results_route._safe_run_dir(".")

    assert exc_info.value.status_code == 400


def test_safe_run_dir_rejects_nested_paths(tmp_path, monkeypatch):
    nested = tmp_path / "run_1" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.setattr(results_route, "RUNS_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        results_route._safe_run_dir("run_1/nested")

    assert exc_info.value.status_code == 400


def test_safe_run_dir_accepts_single_child_directory(tmp_path, monkeypatch):
    run_dir = tmp_path / "run_1"
    run_dir.mkdir()
    monkeypatch.setattr(results_route, "RUNS_DIR", tmp_path)

    assert results_route._safe_run_dir("run_1") == run_dir.resolve()
