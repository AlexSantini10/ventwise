"""Container-side test and coverage entry point shared by local runs and CI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


LAYER_PATHS = {
    "unit": ["tests/unit"],
    "integration": ["tests/integration"],
    "system": ["tests/system"],
    "all": ["tests/unit", "tests/integration", "tests/system"],
}
def _command(*args: str) -> int:
    return subprocess.run(args, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=LAYER_PATHS, default="all")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    pytest_args = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
    artifacts = Path(os.environ.get("VENTWISE_TEST_ARTIFACTS", "/artifacts"))
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("COVERAGE_FILE", "/tmp/.coverage")

    test_exit = _command(
        sys.executable,
        "-m",
        "coverage",
        "run",
        "-m",
        "pytest",
        *LAYER_PATHS[args.layer],
        "-ra",
        "-p",
        "no:cacheprovider",
        "--junitxml",
        str(artifacts / "junit.xml"),
        *pytest_args,
    )
    if test_exit:
        return test_exit
    if _command(sys.executable, "-m", "coverage", "xml", "-o", str(artifacts / "coverage.xml")):
        return 1
    if _command(sys.executable, "-m", "coverage", "html", "-d", str(artifacts / "htmlcov")):
        return 1
    return _command(sys.executable, "-m", "coverage", "report")


if __name__ == "__main__":
    raise SystemExit(main())
