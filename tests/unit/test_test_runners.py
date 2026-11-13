"""Regression tests for the local/CI test-runner contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_runner_exposes_every_documented_layer() -> None:
    runner = _load_script("run_tests")

    assert runner.LAYERS == ("all", "unit", "integration", "system")
    assert runner.COMPOSE_FILE.name == "docker-compose.ci.yml"


def test_container_runner_maps_layers_to_the_expected_directories() -> None:
    runner = _load_script("run_test_suite")

    assert runner.LAYER_PATHS == {
        "unit": ["tests/unit"],
        "integration": ["tests/integration"],
        "system": ["tests/system"],
        "all": ["tests/unit", "tests/integration", "tests/system"],
    }


def test_container_runner_runs_all_layers_in_a_stable_order() -> None:
    runner = _load_script("run_test_suite")

    assert runner.ALL_LAYERS == ("unit", "integration", "system")
