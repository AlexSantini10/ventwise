"""Tests for the local Home Assistant Docker runner."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


RUNNER_PATH = Path(__file__).parents[1] / "ha-local-docker-test.py"
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


def test_verify_mounted_integration_version_rejects_stale_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A container with a stale bind mount must fail before manual testing."""

    monkeypatch.setattr(RUNNER, "mounted_integration_version", lambda _: "0.4.0")

    with pytest.raises(SystemExit, match="expected 0.5.0, container sees 0.4.0"):
        RUNNER.verify_mounted_integration_version("ventwise-ha-test", "0.5.0")
