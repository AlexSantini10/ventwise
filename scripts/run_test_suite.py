"""Container-side test and coverage entry point shared by local runs and CI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


LAYER_PATHS = {
    "unit": ["tests/unit"],
    "integration": ["tests/integration"],
    "system": ["tests/system"],
    "all": ["tests/unit", "tests/integration", "tests/system"],
}
ALL_LAYERS = ("unit", "integration", "system")


def _command(*args: str) -> int:
    return subprocess.run(args, check=False).returncode


def _run_layer(layer: str, pytest_args: list[str], artifacts: Path) -> tuple[int, float]:
    started = time.perf_counter()
    exit_code = _command(
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--parallel-mode",
        "-m",
        "pytest",
        *LAYER_PATHS[layer],
        "-ra",
        "-p",
        "no:cacheprovider",
        "--junitxml",
        str(artifacts / f"junit-{layer}.xml"),
        *pytest_args,
    )
    return exit_code, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=LAYER_PATHS, default="all")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    pytest_args = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
    artifacts = Path(os.environ.get("VENTWISE_TEST_ARTIFACTS", "/artifacts"))
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("COVERAGE_FILE", "/tmp/.coverage")

    layers = (args.layer,) if args.layer != "all" else ALL_LAYERS
    started = time.perf_counter()
    results: dict[str, dict[str, float | int]] = {}
    test_exit = 0
    for layer in layers:
        print(f"Running {layer} tests...", flush=True)
        layer_exit, duration = _run_layer(layer, pytest_args, artifacts)
        results[layer] = {"exit_code": layer_exit, "duration_seconds": round(duration, 3)}
        if layer_exit and not test_exit:
            test_exit = layer_exit

    timing = {
        "layers": results,
        "total_duration_seconds": round(time.perf_counter() - started, 3),
    }
    (artifacts / "timing.json").write_text(
        json.dumps(timing, indent=2) + "\n",
        encoding="utf-8",
    )

    coverage_exit = _command(sys.executable, "-m", "coverage", "combine")
    if not coverage_exit:
        coverage_exit = _command(
            sys.executable, "-m", "coverage", "xml", "-o", str(artifacts / "coverage.xml")
        )
    if not coverage_exit:
        coverage_exit = _command(
            sys.executable, "-m", "coverage", "html", "-d", str(artifacts / "htmlcov")
        )
    if not coverage_exit:
        coverage_exit = _command(sys.executable, "-m", "coverage", "report")

    return test_exit or coverage_exit


if __name__ == "__main__":
    raise SystemExit(main())
