"""Ensure every Home Assistant form field has a user-facing translation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("voluptuous")

from custom_components.ventwise.configuration.flow import (  # noqa: E402
    build_advanced_options_schema,
    build_basic_options_schema,
    build_comfort_schema,
    build_config_schema,
    build_notification_schema,
    build_outdoor_override_schema,
    build_outdoor_source_schema,
    build_override_schema,
    build_room_schema,
    build_settings_schema,
    build_unit_schema,
)
from custom_components.ventwise.const import (  # noqa: E402
    CONF_DIAGNOSTIC_NOTIFICATION_LEVEL,
)


TRANSLATIONS_DIR = Path(__file__).parents[2] / "custom_components" / "ventwise" / "translations"
LOCALES = ("en", "it", "es", "fr", "de", "ru", "zh-Hans")
ROOM_STEPS = (
    ("add_room", "room"),
    ("edit_room_form", "room"),
)
MENU_OPTIONS = {
    "config": {
        "rooms": {"add_room", "edit_room", "remove_room", "finish"},
    },
    "options": {
        "init": {"units", "comfort", "notifications", "overrides", "rooms"},
        "rooms": {"add_room", "edit_room", "remove_room", "finish"},
    },
}


def _load(locale: str) -> dict[str, Any]:
    return json.loads((TRANSLATIONS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


def _field_names(schema) -> set[str]:
    return {
        str(key.schema if hasattr(key, "schema") else key)
        for key in schema.schema
    }


def _schemas() -> dict[tuple[str, str], Any]:
    room_schemas = {
        f"{step}:{kind}": build_room_schema({}, 0, kind)
        for step, kind in ROOM_STEPS
    }
    return {
        ("config", "user"): build_config_schema({}),
        ("config", "units"): build_unit_schema({}),
        ("config", "outdoor"): build_outdoor_source_schema({}),
        ("config", "outdoor_overrides"): build_outdoor_override_schema(
            {
                "outdoor_temperature_override": True,
                "outdoor_humidity_override": True,
                "wind_speed_override": True,
            }
        ),
        ("options", "units"): build_unit_schema({}),
        ("options", "settings"): build_settings_schema({}),
        ("options", "comfort"): build_comfort_schema({}),
        ("options", "notifications"): build_notification_schema({}),
        ("options", "overrides"): build_override_schema({}),
        ("options", "basic"): build_basic_options_schema({}),
        ("options", "advanced"): build_advanced_options_schema({}),
        **{("config", step): schema for step, kind in ROOM_STEPS for schema in [room_schemas[f"{step}:{kind}"]]},
        **{("options", step): schema for step, kind in ROOM_STEPS for schema in [room_schemas[f"{step}:{kind}"]]},
    }


@pytest.mark.parametrize("locale", LOCALES)
def test_every_schema_field_has_a_localized_label(locale: str) -> None:
    translations = _load(locale)
    missing: list[str] = []
    for (section, step), schema in _schemas().items():
        labels = translations[section]["step"].get(step, {}).get("data", {})
        for field in sorted(_field_names(schema)):
            if not labels.get(field) or labels[field] == field:
                missing.append(f"{section}.{step}.data.{field}")
    assert not missing, f"{locale} exposes untranslated field IDs: {missing}"


@pytest.mark.parametrize("locale", LOCALES)
def test_selector_options_have_localized_labels(locale: str) -> None:
    translations = _load(locale)
    schema = build_config_schema({})
    entry = next(
        key for key in schema.schema
        if getattr(key, "schema", key) == CONF_DIAGNOSTIC_NOTIFICATION_LEVEL
    )
    options = set(schema.schema[entry].config["options"])
    labels = translations["selector"]["diagnostic_notification_level"]["options"]
    missing = sorted(option for option in options if not labels.get(option))
    assert not missing, f"{locale} is missing selector labels: {missing}"


@pytest.mark.parametrize("locale", LOCALES)
def test_menu_options_have_localized_labels(locale: str) -> None:
    translations = _load(locale)
    missing: list[str] = []
    for section, menus in MENU_OPTIONS.items():
        for step, options in menus.items():
            labels = translations[section]["step"].get(step, {}).get("menu_options", {})
            missing.extend(
                f"{section}.{step}.menu_options.{option}"
                for option in sorted(options)
                if not labels.get(option)
            )
    assert not missing, f"{locale} exposes untranslated menu IDs: {missing}"


@pytest.mark.parametrize("schema_name", ("comfort", "notifications", "overrides"))
def test_split_options_schemas_do_not_expose_unrelated_fields(schema_name: str) -> None:
    schemas = _schemas()
    fields = _field_names(schemas[("options", schema_name)])
    expected_groups = {
        "comfort": {
            "target_temperature_c",
            "auto_comfort_temperature",
            "target_humidity_percent",
            "stability_minutes",
            "soft_outdoor_threshold_c",
            "co2_enabled",
            "co2_entity_id",
            "co2_threshold_ppm",
        },
        "notifications": {
            "notification_device_id",
            "home_assistant_notification_enabled",
            "diagnostic_notification_level",
            "debug_mode_enabled",
            "safety_bypass_quiet_hours",
            "cooldown_minutes",
        },
        "overrides": {
            "outdoor_weather_entity_id",
            "outdoor_temperature_override",
            "outdoor_humidity_override",
            "wind_speed_override",
            "outdoor_temperature_entity_id",
            "outdoor_humidity_entity_id",
            "wind_speed_entity_id",
        },
    }
    assert fields == expected_groups[schema_name]
