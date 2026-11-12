"""Regression tests for the shared VentWise diagnostic contract."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.ventwise.errors import ErrorCategory, error_reference


def test_error_categories_are_stable_and_complete() -> None:
    assert {item.value for item in ErrorCategory} == {
        "validation",
        "configuration",
        "source_unavailable",
        "delivery",
        "unexpected",
    }


def test_error_reference_is_safe_and_stable() -> None:
    reference = error_reference("coordinator.refresh", RuntimeError("secret token"))
    assert reference == error_reference("coordinator.refresh", RuntimeError("other detail"))
    assert len(reference) == 12
    assert "secret" not in reference


def test_runtime_diagnostic_translations_have_the_same_error_keys() -> None:
    catalogs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (Path(__file__).parents[2] / "custom_components/ventwise/translations/runtime").glob("*.json")
    ]
    expected = {"unavailable_data", "no_enabled_rooms", "provider_unavailable", "unexpected_error"}
    assert catalogs
    assert all(set(catalog["diagnostic"]) == expected for catalog in catalogs)
