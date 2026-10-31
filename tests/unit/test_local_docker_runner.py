"""Tests for the local Home Assistant Docker runner."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


RUNNER_PATH = Path(__file__).parents[2] / "scripts" / "ha-local-docker-test.py"
SPEC = importlib.util.spec_from_file_location("ventwise_local_docker_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_integration_version_reads_the_local_manifest(tmp_path: Path) -> None:
    """The displayed test version must come from the mounted source manifest."""

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"version": "9.8.7"}), encoding="utf-8")

    assert RUNNER.integration_version(tmp_path) == "9.8.7"


def test_integration_version_rejects_a_missing_manifest_version(tmp_path: Path) -> None:
    """A malformed source must not silently start an ambiguous test run."""

    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="no usable version"):
        RUNNER.integration_version(tmp_path)


def test_verify_mounted_integration_version_rejects_stale_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A container with a stale installed package must fail before testing."""

    monkeypatch.setattr(RUNNER, "mounted_integration_version", lambda _: "0.4.0")

    with pytest.raises(SystemExit, match="expected 0.5.0, container sees 0.4.0"):
        RUNNER.verify_mounted_integration_version("ventwise-ha-test", "0.5.0")


def test_install_package_uses_only_the_distributable_integration_files(tmp_path: Path) -> None:
    """The Lab must not use a source mount or install release root files as code."""

    package_path = tmp_path / "ventwise.zip"
    with ZipFile(package_path, "w") as package:
        package.writestr("manifest.json", json.dumps({"version": "1.2.3"}))
        package.writestr("sensor.py", "SENSOR = True\n")
        package.writestr("translations/en.json", "{}")
        package.writestr("README.md", "release notes")

    installed = RUNNER.install_package(package_path, tmp_path / "profile" / "config")

    assert json.loads((installed / "manifest.json").read_text(encoding="utf-8"))["version"] == "1.2.3"
    assert (installed / "sensor.py").exists()
    assert (installed / "translations" / "en.json").exists()
    assert not (installed / "README.md").exists()


def test_ensure_config_provisions_the_complete_manual_lab(tmp_path: Path) -> None:
    """The isolated profile exposes fixtures and actionable Lab controls."""

    config_dir = RUNNER.ensure_config(tmp_path)
    config_text = (config_dir / "configuration.yaml").read_text(encoding="utf-8")

    assert "ventwise_lab_bootstrap:" in config_text
    assert "input_boolean: !include ventwise_test_booleans.yaml" in config_text
    dashboard = (config_dir / "ventwise_test_dashboard.yaml").read_text(encoding="utf-8")
    assert "input_number.ventwise_test_bedroom_co2" in dashboard
    assert "button.ventwise_test_lab_request_recommendation" in dashboard
    assert "switch.ventwise_test_lab_quiet_hours_enable" in dashboard
    assert "sensor.camera_test_recommendation" in dashboard
    assert (config_dir / "custom_components" / "ventwise_lab_bootstrap" / "__init__.py").exists()
