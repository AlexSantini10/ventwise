"""Regression tests for Home Assistant UI translations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


TRANSLATIONS_DIR = Path(__file__).parents[1] / "custom_components" / "ventwise" / "translations"


def _load_translation(language: str) -> dict[str, Any]:
    """Load a translation file while rejecting duplicate JSON keys."""

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate translation key: {key}")
            result[key] = value
        return result

    return json.loads(
        (TRANSLATIONS_DIR / f"{language}.json").read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


def _leaf_paths(value: Any, prefix: str = "") -> set[str]:
    """Return every leaf path in a nested translation mapping."""

    if not isinstance(value, dict):
        return {prefix}
    return {
        path
        for key, child in value.items()
        for path in _leaf_paths(child, f"{prefix}.{key}" if prefix else key)
    }


def test_translation_files_are_valid_and_have_matching_keys() -> None:
    """Keep the Italian UI aligned with the English source of truth."""

    english = _load_translation("en")
    italian = _load_translation("it")

    assert _leaf_paths(italian) == _leaf_paths(english)


def test_translation_files_reject_duplicate_keys() -> None:
    """Make a duplicate key a visible test failure instead of silently overriding it."""

    for language in ("en", "it"):
        try:
            _load_translation(language)
        except ValueError as error:
            pytest.fail(f"{language}.json is invalid: {error}")
