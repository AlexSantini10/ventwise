"""Regression tests for Home Assistant UI translations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


TRANSLATIONS_DIR = Path(__file__).parents[2] / "custom_components" / "ventwise" / "translations"


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


REVIEWED_LANGUAGES = ("it", "es", "ru", "zh-Hans", "fr", "de")
ROOM_FORM_STEPS = (
    "add_room",
    "edit_room_form",
    "add_macro_room",
    "edit_macro_room_form",
)
DDP_RECOMMENDATION_ATTRIBUTES = (
    "core_action", "delivered_action", "duration_minutes", "confidence",
    "candidates", "trace", "blocked_conditions", "applied_penalties",
    "data_quality", "delivery_suppressed_by",
)
OBSOLETE_STEPS = {"settings", "basic", "edit_room_select", "remove_room_select"}
REQUIRED_MENU_OPTIONS = {
    ("config", "rooms"): {"add_room", "add_macro_room", "edit_room", "remove_room", "finish"},
    ("options", "init"): {"daily", "rooms", "advanced", "units"},
    ("options", "advanced"): {"recommendations", "manual_sources", "air_quality", "diagnostics"},
    ("options", "air_quality"): {"air_quality_global", "air_quality_source_select"},
    ("options", "edit_room_details"): {"edit_room_base", "edit_room_advanced"},
}


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


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_reachable_menus_have_complete_non_empty_labels(language: str) -> None:
    """Every menu emitted by a flow must have a label and description."""

    translation = _load_translation(language)
    for (section, step_id), expected in REQUIRED_MENU_OPTIONS.items():
        step = translation[section]["step"][step_id]
        assert set(step["menu_options"]) == expected
        assert set(step["menu_option_descriptions"]) == expected
        assert all(step["menu_options"].values())
        assert all(step["menu_option_descriptions"].values())


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_translation_values_are_not_empty_or_corrupted(language: str) -> None:
    """Reject the placeholder strings that previously hid form controls."""

    def leaves(value: Any):
        if isinstance(value, dict):
            for child in value.values():
                yield from leaves(child)
        elif isinstance(value, str):
            yield value

    values = list(leaves(_load_translation(language)))
    assert all(value.strip() for value in values)
    assert not any("�" in value or "??" in value or "CO?" in value for value in values)


@pytest.mark.parametrize("language", ("en", *REVIEWED_LANGUAGES))
def test_obsolete_flow_steps_are_not_translated(language: str) -> None:
    """Keep removed flow IDs from reappearing as dead UI entries."""

    translation = _load_translation(language)
    for section in ("config", "options"):
        assert not OBSOLETE_STEPS.intersection(translation[section]["step"])


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
def test_ddp_forms_and_recommendation_attributes_are_localized(language: str) -> None:
    """Keep DDP controls and its user-facing explanation translatable."""

    translation = _load_translation(language)
    steps = translation["options"]["step"]
    for step, field in (
        ("air_quality_global", "smoke_alert_entity_id"),
        ("air_quality_global", "pollution_policy"),
        ("air_quality_global", "pollen_policy"),
        ("air_quality_global", "open_meteo_air_quality_enabled"),
        ("air_quality_source", "air_quality_entity_id"),
        ("air_quality_source", "air_quality_averaging_period"),
    ):
        assert steps[step]["data"][field]
    for section in ("config", "options"):
        for step in ROOM_FORM_STEPS:
            assert translation[section]["step"][step]["data"]["co2_entity_id"]
    attributes = translation["entity"]["sensor"]["recommendation"]["state_attributes"]
    for attribute in DDP_RECOMMENDATION_ATTRIBUTES:
        assert attributes[attribute]["name"]


def test_adaptive_comfort_help_explains_the_calculation_and_control_boundary() -> None:
    """Keep the native setup and options help specific and safe for users."""

    english = _load_translation("en")
    italian = _load_translation("it")
    russian = _load_translation("ru")
    english_help = (
        english["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        english["options"]["step"]["daily"]["data_description"][
            "auto_comfort_temperature"
        ],
    )
    italian_help = (
        italian["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        italian["options"]["step"]["daily"]["data_description"][
            "auto_comfort_temperature"
        ],
    )

    russian_help = (
        russian["config"]["step"]["user"]["data_description"]["auto_comfort_temperature"],
        russian["options"]["step"]["daily"]["data_description"][
            "auto_comfort_temperature"
        ],
    )

    for description in english_help:
        assert "±2°C" in description
        assert "18–26°C" in description
        assert "thermostat or HVAC" in description
    for description in (*italian_help, *russian_help):
        assert description
        assert "18" in description and "26" in description
