"""Regression tests for Home Assistant UI translations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


TRANSLATIONS_DIR = Path(__file__).parents[2] / "custom_components" / "ventwise" / "translations"
NATIVE_STRINGS_PATH = TRANSLATIONS_DIR.parent / "strings.json"


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


def _leaf_values(value: Any, prefix: str = "") -> dict[str, str]:
    """Return string leaves keyed by their nested translation path."""

    if isinstance(value, str):
        return {prefix: value}
    if not isinstance(value, dict):
        return {}
    return {
        path: child
        for key, nested in value.items()
        for path, child in _leaf_values(nested, f"{prefix}.{key}" if prefix else key).items()
    }


REVIEWED_LANGUAGES = ("it", "es", "ru", "zh-Hans", "fr", "de")
ROOM_FORM_STEPS = (
    "add_room",
    "edit_room_form",
)


@pytest.mark.parametrize("language", REVIEWED_LANGUAGES)
def test_translation_files_are_valid_and_have_matching_keys(language: str) -> None:
    """Keep each reviewed locale aligned with the English source of truth."""

    english = _load_translation("en")
    localized = _load_translation(language)

    assert _leaf_paths(localized) == _leaf_paths(english)


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_translation_files_reject_duplicate_keys(language: str) -> None:
    """Make a duplicate key a visible test failure instead of silently overriding it."""

    try:
        _load_translation(language)
    except ValueError as error:
        pytest.fail(f"{language}.json is invalid: {error}")


def test_native_strings_catalog_covers_entity_translations() -> None:
    """Ensure Home Assistant can resolve every translated entity key."""

    native = json.loads(NATIVE_STRINGS_PATH.read_text(encoding="utf-8"))
    english = _load_translation("en")
    assert _leaf_paths(native["entity"]) == _leaf_paths(english["entity"])


@pytest.mark.parametrize("language", REVIEWED_LANGUAGES)
def test_localized_catalogs_do_not_copy_english_user_facing_values(language: str) -> None:
    """Catch untranslated UI strings while allowing the integration title."""

    english = _leaf_values(_load_translation("en"))
    localized = _leaf_values(_load_translation(language))
    copied = {
        path
        for path, value in localized.items()
        if path != "title" and value == english.get(path)
    }

    assert not copied, f"{language} copies English UI values: {sorted(copied)}"


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_room_forms_localize_the_window_contacts_field(language: str) -> None:
    """Keep the optional contact picker readable in every supported UI locale."""

    translation = _load_translation(language)
    for section in ("config", "options"):
        for step in ROOM_FORM_STEPS:
            assert (
                translation[section]["step"][step]["data"]["window_sensor_entity_ids"]
            )


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_room_forms_localize_optional_co2_sensor(language: str) -> None:
    """Keep the optional room CO2 selector from falling back to its field ID."""

    translation = _load_translation(language)
    for section in ("config", "options"):
        for step in ROOM_FORM_STEPS:
            form = translation[section]["step"][step]
            assert form["data"]["co2_entity_id"]
            assert form["data_description"]["co2_entity_id"]


def test_adaptive_comfort_help_explains_the_calculation_and_control_boundary() -> None:
    """Keep the native setup and options help specific and safe for users."""

    english = _load_translation("en")
    italian = _load_translation("it")
    russian = _load_translation("ru")
    english_help = (
        english["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        english["options"]["step"]["settings"]["data_description"][
            "auto_comfort_temperature"
        ],
    )
    italian_help = (
        italian["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        italian["options"]["step"]["settings"]["data_description"][
            "auto_comfort_temperature"
        ],
    )

    russian_help = (
        russian["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        russian["options"]["step"]["settings"]["data_description"][
            "auto_comfort_temperature"
        ],
    )

    for description in english_help:
        assert "±2°C" in description
        assert "18–26°C" in description
        assert "thermostat or HVAC" in description
    for description in italian_help:
        assert "±2 °C" in description
        assert "18–26 °C" in description
        assert "termostato o HVAC" in description
    for description in russian_help:
        assert "±2 °C" in description
        assert "18–26 °C" in description
        assert "термостатом" in description
        assert "HVAC" in description
