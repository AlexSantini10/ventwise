"""Pytest configuration for the core package."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_collection_modifyitems(items) -> None:
    """Apply the layer marker from the stable test-directory convention."""

    for item in items:
        parts = item.path.parts
        for layer in ("unit", "integration", "system"):
            if layer in parts:
                item.add_marker(layer)
                break
