"""Release package contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import os
import subprocess
import sys
from zipfile import ZipFile


SCRIPT = Path(__file__).parents[2] / "scripts" / "build_release_package.py"
SPEC = importlib.util.spec_from_file_location("ventwise_release_package", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


def test_release_package_embeds_the_standalone_core_at_the_integration_root(tmp_path: Path) -> None:
    output = tmp_path / "ventwise.zip"
    PACKAGE.build_package(Path(__file__).parents[2], output)

    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "ventwise_core/__init__.py" in names
        assert "ventwise_core/__main__.py" in names
        assert "ventwise_core/engine/decision_engine.py" in names
        assert "ventwise_core/serialization/json_codec.py" in names
        assert "decision.py" not in names
        assert "custom_components/ventwise/ventwise_core/decision.py" not in names
        assert "ventwise_core/engine/decision_engine.py" in names
        assert "ModuleNotFoundError" not in archive.read("ventwise_core/__init__.py").decode()


def test_release_package_contains_config_flow_when_manifest_enables_it(tmp_path: Path) -> None:
    output = tmp_path / "ventwise.zip"
    PACKAGE.build_package(Path(__file__).parents[2], output)

    with ZipFile(output) as archive:
        assert "config_flow.py" in archive.namelist()


def test_release_package_core_runs_without_the_repository_on_pythonpath(tmp_path: Path) -> None:
    output = tmp_path / "ventwise.zip"
    extracted = tmp_path / "package"
    PACKAGE.build_package(Path(__file__).parents[2], output)

    with ZipFile(output) as archive:
        archive.extractall(extracted)

    scenario = extracted / "scenario.json"
    scenario.write_text(
        '{"evaluated_at":"2026-11-17T12:00:00+00:00",'
        '"rooms":[],"outdoor":{"temperature_c":null,"humidity_percent":null}}',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ventwise_core", str(scenario)],
        cwd=extracted,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"schema_version":"ventwise.engine.v3"' in result.stdout
