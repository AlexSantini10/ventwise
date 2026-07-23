"""Tests for config flow helper schemas and normalization."""

from __future__ import annotations

import pytest

pytest.importorskip("voluptuous")
pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_COOLDOWN_MINUTES,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_SOURCE,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_SOURCE,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_END_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_PAUSE_ENTITY_ID,
    CONF_QUIET_HOURS_START,
    CONF_QUIET_HOURS_START_ENTITY_ID,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_PAUSE_ENTITY_ID,
    CONF_ROOM_START_ENTITY_ID,
    CONF_ROOM_STOP_ENTITY_ID,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WEIGHT,
    CONF_ROOMS,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_TEMPERATURE_C,
    CONF_MASTER_CONTROL_ENTITY_ID,
    CONF_WIND_SPEED_ENTITY_ID,
    CONF_WIND_SPEED_SOURCE,
    OUTDOOR_SOURCE_FORECAST,
    OUTDOOR_SOURCE_OVERRIDE,
)
from custom_components.ventwise.flow import (
    ConfigValidationError,
    build_advanced_options_schema,
    build_basic_options_schema,
    build_outdoor_override_schema,
    build_outdoor_source_schema,
    build_config_schema,
    build_room_schema,
    normalize_advanced_config,
    normalize_basic_config,
    normalize_outdoor_override_config,
    normalize_outdoor_source_config,
    normalize_room_config,
    normalize_setup_overrides_config,
    split_config_data,
)


def _schema_entry(schema, field_name: str):
    return next(entry for entry in schema.schema if getattr(entry, "schema", None) == field_name)


def _schema_default(entry):
    default = entry.default
    return default() if callable(default) else default


def test_config_schema_is_simple_and_weather_based() -> None:
    """The initial setup should ask for weather and comfort temperature."""

    schema = build_config_schema({})
    schema_dict = schema.schema

    assert schema_dict[CONF_OUTDOOR_WEATHER_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_TARGET_TEMPERATURE_C].__class__.__name__ == "All"
    assert schema_dict[CONF_NOTIFICATION_DEVICE_ID].__class__.__name__ == "Any"


def test_setup_overrides_schema_is_source_selector_based() -> None:
    """The outdoor step should ask for a source per measurement."""

    schema = build_outdoor_source_schema({})
    schema_dict = schema.schema

    assert schema_dict[CONF_OUTDOOR_TEMPERATURE_SOURCE].__class__.__name__ == "SelectSelector"
    assert schema_dict[CONF_OUTDOOR_HUMIDITY_SOURCE].__class__.__name__ == "SelectSelector"
    assert schema_dict[CONF_WIND_SPEED_SOURCE].__class__.__name__ == "SelectSelector"


def test_outdoor_override_schema_only_exposes_selected_entities() -> None:
    """Only the measurements marked as overrides should ask for entities."""

    schema = build_outdoor_override_schema(
        {
            CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
            CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
        }
    )
    schema_dict = schema.schema

    assert schema_dict[CONF_OUTDOOR_TEMPERATURE_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert CONF_OUTDOOR_HUMIDITY_ENTITY_ID not in schema_dict
    assert schema_dict[CONF_WIND_SPEED_ENTITY_ID].__class__.__name__ == "EntitySelector"


def test_basic_options_schema_covers_simple_controls() -> None:
    """The basic options step should stay approachable."""

    schema = build_basic_options_schema({})
    schema_dict = schema.schema

    assert schema_dict[CONF_OUTDOOR_WEATHER_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_TARGET_TEMPERATURE_C].__class__.__name__ == "All"
    assert callable(schema_dict[CONF_QUIET_HOURS_ENABLED])
    assert schema_dict[CONF_QUIET_HOURS_PAUSE_ENTITY_ID].__class__.__name__ == "Any"
    assert schema_dict[CONF_NOTIFICATION_DEVICE_ID].__class__.__name__ == "Any"


def test_advanced_options_schema_contains_the_technical_overrides() -> None:
    """The advanced step should carry the detailed tuning controls."""

    schema = build_advanced_options_schema({})
    schema_dict = schema.schema

    assert schema_dict[CONF_SOFT_OUTDOOR_THRESHOLD_C].__class__.__name__ == "All"
    assert schema_dict[CONF_STABILITY_MINUTES].__class__.__name__ == "All"
    assert schema_dict[CONF_QUIET_HOURS_START].__class__.__name__ == "TextSelector"
    assert schema_dict[CONF_QUIET_HOURS_END].__class__.__name__ == "TextSelector"
    assert schema_dict[CONF_QUIET_HOURS_START_ENTITY_ID].__class__.__name__ == "Any"
    assert schema_dict[CONF_QUIET_HOURS_END_ENTITY_ID].__class__.__name__ == "Any"
    assert schema_dict[CONF_MASTER_CONTROL_ENTITY_ID].__class__.__name__ == "Any"
    assert CONF_OUTDOOR_TEMPERATURE_ENTITY_ID not in schema_dict
    assert CONF_OUTDOOR_HUMIDITY_ENTITY_ID not in schema_dict
    assert CONF_WIND_SPEED_ENTITY_ID not in schema_dict


def test_room_schema_supports_room_and_macro_room_defaults() -> None:
    """Room-like entries should share the same structure."""

    room_schema = build_room_schema({}, 0, "room")
    macro_schema = build_room_schema({}, 0, "macro_room")

    assert _schema_default(_schema_entry(room_schema, CONF_ROOM_NAME)) == "Room 1"
    assert _schema_default(_schema_entry(macro_schema, CONF_ROOM_NAME)) == "Macro Room 1"
    assert room_schema.schema[CONF_ROOM_TEMPERATURE_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert room_schema.schema[CONF_ROOM_HUMIDITY_ENTITY_ID].__class__.__name__ == "Any"
    assert room_schema.schema[CONF_ROOM_WEIGHT].__class__.__name__ == "All"
    assert room_schema.schema[CONF_ROOM_START_ENTITY_ID].__class__.__name__ == "Any"
    assert room_schema.schema[CONF_ROOM_STOP_ENTITY_ID].__class__.__name__ == "Any"
    assert room_schema.schema[CONF_ROOM_PAUSE_ENTITY_ID].__class__.__name__ == "Any"


def test_normalize_basic_config_strips_optional_entities() -> None:
    """Optional basic values should be normalized to clean strings or None."""

    data = normalize_basic_config(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_TARGET_TEMPERATURE_C: "22.5",
            CONF_QUIET_HOURS_PAUSE_ENTITY_ID: " ",
            CONF_NOTIFICATION_DEVICE_ID: None,
        }
    )

    assert data[CONF_OUTDOOR_WEATHER_ENTITY_ID] == "weather.home"
    assert data[CONF_TARGET_TEMPERATURE_C] == 22.5
    assert data[CONF_QUIET_HOURS_PAUSE_ENTITY_ID] is None
    assert data[CONF_NOTIFICATION_DEVICE_ID] is None


def test_normalize_outdoor_source_config_defaults_and_clears_overrides() -> None:
    data = normalize_outdoor_source_config(
        {
            CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
            CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
        }
    )

    assert data[CONF_OUTDOOR_TEMPERATURE_SOURCE] == OUTDOOR_SOURCE_OVERRIDE
    assert data[CONF_OUTDOOR_HUMIDITY_SOURCE] == OUTDOOR_SOURCE_FORECAST
    assert data[CONF_WIND_SPEED_SOURCE] == OUTDOOR_SOURCE_OVERRIDE
    assert data[CONF_OUTDOOR_HUMIDITY_ENTITY_ID] is None


def test_normalize_outdoor_override_config_accepts_input_number_entities() -> None:
    data = normalize_outdoor_override_config(
        {
            CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "input_number.outdoor_temp",
            CONF_WIND_SPEED_ENTITY_ID: "input_number.wind_speed",
        },
        {
            CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
            CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
        },
    )

    assert data[CONF_OUTDOOR_TEMPERATURE_ENTITY_ID] == "input_number.outdoor_temp"
    assert data[CONF_OUTDOOR_HUMIDITY_ENTITY_ID] is None
    assert data[CONF_WIND_SPEED_ENTITY_ID] == "input_number.wind_speed"


def test_normalize_setup_overrides_config_accepts_sources() -> None:
    data = normalize_setup_overrides_config(
        {
            CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
            CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
        }
    )

    assert data[CONF_OUTDOOR_TEMPERATURE_SOURCE] == OUTDOOR_SOURCE_OVERRIDE
    assert data[CONF_OUTDOOR_HUMIDITY_SOURCE] == OUTDOOR_SOURCE_FORECAST
    assert data[CONF_WIND_SPEED_SOURCE] == OUTDOOR_SOURCE_OVERRIDE


def test_normalize_basic_config_rejects_missing_weather_source() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_basic_config({})

    assert exc_info.value.field == CONF_OUTDOOR_WEATHER_ENTITY_ID


def test_normalize_basic_config_rejects_invalid_weather_domain() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_basic_config(
            {
                CONF_OUTDOOR_WEATHER_ENTITY_ID: "sensor.home",
                CONF_TARGET_TEMPERATURE_C: 22.0,
            }
        )

    assert exc_info.value.field == CONF_OUTDOOR_WEATHER_ENTITY_ID


def test_normalize_outdoor_override_config_rejects_invalid_outdoor_sensor_domain() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_outdoor_override_config(
            {
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "binary_sensor.outdoor_temp",
            }
            ,
            {
                CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
                CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
                CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_FORECAST,
            },
        )

    assert exc_info.value.field == CONF_OUTDOOR_TEMPERATURE_ENTITY_ID


def test_normalize_outdoor_override_config_rejects_non_numeric_outdoor_entity() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_outdoor_override_config(
            {
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "light.outdoor_temp",
            },
            {
                CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
                CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_FORECAST,
                CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_FORECAST,
            }
        )

    assert exc_info.value.field == CONF_OUTDOOR_TEMPERATURE_ENTITY_ID


def test_normalize_basic_config_rejects_invalid_target_temperature() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_basic_config(
            {
                CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
                CONF_TARGET_TEMPERATURE_C: 5.0,
            }
        )

    assert exc_info.value.field == CONF_TARGET_TEMPERATURE_C


def test_normalize_advanced_config_normalizes_times_and_entities() -> None:
    """Advanced settings should accept short times and trim optional entities."""

    data = normalize_advanced_config(
        {
            CONF_SOFT_OUTDOOR_THRESHOLD_C: 24.0,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_STABILITY_MINUTES: 10,
            CONF_QUIET_HOURS_START: "22:00",
            CONF_QUIET_HOURS_END: "07:00:00",
            CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "input_number.outdoor_temp",
            CONF_OUTDOOR_HUMIDITY_ENTITY_ID: "sensor.outdoor_humidity",
            CONF_WIND_SPEED_ENTITY_ID: "input_number.wind_speed",
            CONF_QUIET_HOURS_START_ENTITY_ID: " input_datetime.quiet_start ",
            CONF_QUIET_HOURS_END_ENTITY_ID: "",
            CONF_MASTER_CONTROL_ENTITY_ID: " input_boolean.master ",
        }
    )

    assert data[CONF_QUIET_HOURS_START] == "22:00:00"
    assert data[CONF_QUIET_HOURS_END] == "07:00:00"
    assert data[CONF_OUTDOOR_TEMPERATURE_ENTITY_ID] == "input_number.outdoor_temp"
    assert data[CONF_OUTDOOR_HUMIDITY_ENTITY_ID] == "sensor.outdoor_humidity"
    assert data[CONF_WIND_SPEED_ENTITY_ID] == "input_number.wind_speed"
    assert data[CONF_QUIET_HOURS_START_ENTITY_ID] == "input_datetime.quiet_start"
    assert data[CONF_QUIET_HOURS_END_ENTITY_ID] is None
    assert data[CONF_MASTER_CONTROL_ENTITY_ID] == "input_boolean.master"


def test_normalize_advanced_config_rejects_invalid_time_format() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_advanced_config(
            {
                CONF_SOFT_OUTDOOR_THRESHOLD_C: 24.0,
                CONF_COOLDOWN_MINUTES: 60,
                CONF_STABILITY_MINUTES: 10,
                CONF_QUIET_HOURS_START: "25:00",
                CONF_QUIET_HOURS_END: "07:00",
            }
        )

    assert exc_info.value.field == CONF_QUIET_HOURS_START


def test_normalize_advanced_config_rejects_out_of_range_numeric_values() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_advanced_config(
            {
                CONF_QUIET_HOURS_START: "22:00",
                CONF_QUIET_HOURS_END: "07:00",
                CONF_SOFT_OUTDOOR_THRESHOLD_C: 60.0,
                CONF_COOLDOWN_MINUTES: 60,
                CONF_STABILITY_MINUTES: 10,
            }
        )

    assert exc_info.value.field == CONF_SOFT_OUTDOOR_THRESHOLD_C


def test_normalize_room_config_sets_kind_and_trims_names() -> None:
    """Room data should keep the room kind while trimming free text."""

    data = normalize_room_config(
        {
            CONF_ROOM_NAME: "  Bedroom  ",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temp",
            CONF_ROOM_HUMIDITY_ENTITY_ID: " ",
            CONF_ROOM_WEIGHT: 1.25,
            CONF_ROOM_START_ENTITY_ID: "automation.start_room",
            CONF_ROOM_STOP_ENTITY_ID: "",
            CONF_ROOM_PAUSE_ENTITY_ID: "input_boolean.room_pause",
        },
        "macro_room",
    )

    assert data[CONF_ROOM_KIND] == "macro_room"
    assert data[CONF_ROOM_NAME] == "Bedroom"
    assert data[CONF_ROOM_WEIGHT] == 1.25
    assert data[CONF_ROOM_HUMIDITY_ENTITY_ID] is None
    assert data[CONF_ROOM_START_ENTITY_ID] == "automation.start_room"
    assert data[CONF_ROOM_STOP_ENTITY_ID] is None
    assert data[CONF_ROOM_PAUSE_ENTITY_ID] == "input_boolean.room_pause"


def test_normalize_room_config_rejects_invalid_room_kind() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_room_config(
            {
                CONF_ROOM_NAME: "Bedroom",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temp",
            },
            "invalid",
        )

    assert exc_info.value.field == CONF_ROOM_KIND


def test_normalize_room_config_rejects_invalid_temperature_entity() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_room_config(
            {
                CONF_ROOM_NAME: "Bedroom",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "switch.bedroom_temp",
                CONF_ROOM_WEIGHT: 1.0,
            },
            "room",
        )

    assert exc_info.value.field == CONF_ROOM_TEMPERATURE_ENTITY_ID


def test_normalize_room_config_accepts_input_number_temperature_and_humidity() -> None:
    data = normalize_room_config(
        {
            CONF_ROOM_NAME: "Bedroom",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "input_number.bedroom_temp",
            CONF_ROOM_HUMIDITY_ENTITY_ID: "input_number.bedroom_humidity",
            CONF_ROOM_WEIGHT: 1.0,
        },
        "room",
    )

    assert data[CONF_ROOM_TEMPERATURE_ENTITY_ID] == "input_number.bedroom_temp"
    assert data[CONF_ROOM_HUMIDITY_ENTITY_ID] == "input_number.bedroom_humidity"


def test_normalize_room_config_rejects_invalid_weight() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        normalize_room_config(
            {
                CONF_ROOM_NAME: "Bedroom",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temp",
                CONF_ROOM_WEIGHT: 0.01,
            },
            "room",
        )

    assert exc_info.value.field == CONF_ROOM_WEIGHT


def test_split_config_data_separates_rooms_from_global_settings() -> None:
    """Persisted config should split cleanly into global and room settings."""

    global_data, rooms = split_config_data(
        {
            CONF_QUIET_HOURS_START: "22:00:00",
            CONF_QUIET_HOURS_END: "07:00:00",
            "other": "value",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                }
            ],
        }
    )

    assert CONF_ROOMS not in global_data
    assert global_data["other"] == "value"
    assert rooms[0][CONF_ROOM_NAME] == "Living room"


def test_split_config_data_returns_copies_of_rooms() -> None:
    """Room dicts should be copied when splitting persisted config."""

    saved = {
        CONF_ROOMS: [
            {
                CONF_ROOM_NAME: "Living room",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                CONF_ROOM_WEIGHT: 2.0,
            }
        ]
    }

    _, rooms = split_config_data(saved)
    saved[CONF_ROOMS][0][CONF_ROOM_NAME] = "Mutated"

    assert rooms[0][CONF_ROOM_NAME] == "Living room"
