"""Release package contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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
        assert "ventwise_core/decision.py" in names
        assert "ventwise_core/serialization.py" in names
        assert "decision.py" not in names
        assert "custom_components/ventwise/ventwise_core/decision.py" not in names
        assert "ventwise_core/decision.py" in names
        assert "ModuleNotFoundError" not in archive.read("ventwise_core/__init__.py").decode()
