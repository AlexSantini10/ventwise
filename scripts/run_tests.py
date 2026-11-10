"""Run VentWise's reproducible automated test suite through Docker Compose."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.ci.yml"
ARTIFACTS = ROOT / ".test-artifacts"
LAYERS = ("all", "unit", "integration", "system")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the same isolated pytest suite used by GitHub Actions."
    )
    parser.add_argument("--layer", choices=LAYERS, default="all")
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to pytest; prefix them with --.",
    )
    return parser.parse_args()


def _run(command: list[str], *, env: dict[str, str]) -> int:
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def main() -> int:
    args = _parse_args()
    if shutil.which("docker") is None:
        print("Docker is required. Install Docker Desktop/Engine and enable Docker Compose.", file=sys.stderr)
        return 2

    probe = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        detail = probe.stderr.strip() or "the Docker daemon is not running"
        print(f"Docker is unavailable: {detail}", file=sys.stderr)
        return 2

    ARTIFACTS.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["VENTWISE_TEST_ARTIFACTS"] = str(ARTIFACTS.resolve())
    compose = ["docker", "compose", "-p", "ventwise-test", "-f", str(COMPOSE_FILE)]
    command = [
        *compose,
        "run",
        "--rm",
        "--build",
        "ci",
        "python",
        "scripts/run_test_suite.py",
        "--layer",
        args.layer,
        *args.pytest_args,
    ]
    try:
        return _run(command, env=env)
    finally:
        _run([*compose, "down", "--remove-orphans"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
