"""Tests for config flow helper schemas and normalization."""

from __future__ import annotations

import pytest

pytest.importorskip("voluptuous")
pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_MASTER_CONTROL_ENTITY_ID,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WEIGHT,
    CONF_WIND_SPEED_ENTITY_ID,
)
from custom_components.ventwise.flow import (
    build_global_schema,
    build_room_schema,
    normalize_global_config,
    normalize_room_config,
    split_config_data,
)


def _schema_entry(schema, field_name: str):
    return next(entry for entry in schema.schema if getattr(entry, "schema", None) == field_name)


def test_global_schema_is_serializable() -> None:
    """The global form should use HA-serializable selectors and validators."""

    schema = build_global_schema({})
    schema_dict = schema.schema

    assert schema_dict[CONF_QUIET_HOURS_START].__class__.__name__ == "TextSelector"
    assert schema_dict[CONF_QUIET_HOURS_END].__class__.__name__ == "TextSelector"
    assert schema_dict[CONF_OUTDOOR_TEMPERATURE_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_OUTDOOR_HUMIDITY_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_NOTIFICATION_DEVICE_ID].__class__.__name__ == "DeviceSelector"
    assert schema_dict[CONF_ROOM_COUNT].__class__.__name__ == "All"


def test_global_schema_defaults_are_stable() -> None:
    """Default values should remain aligned with the integration constants."""

    schema = build_global_schema({})

    assert _schema_entry(schema, CONF_QUIET_HOURS_START).default == "22:00:00"
    assert _schema_entry(schema, CONF_QUIET_HOURS_END).default == "07:00:00"
    assert _schema_entry(schema, CONF_ROOM_COUNT).default == 1


def test_global_schema_honors_supplied_defaults() -> None:
    """Previously saved global values should show back up in the form."""

    schema = build_global_schema(
        {
            CONF_QUIET_HOURS_START: "21:30:00",
            CONF_QUIET_HOURS_END: "06:15:00",
            CONF_NOTIFICATION_DEVICE_ID: "device-123",
        }
    )

    assert _schema_entry(schema, CONF_QUIET_HOURS_START).default == "21:30:00"
    assert _schema_entry(schema, CONF_QUIET_HOURS_END).default == "06:15:00"
    assert _schema_entry(schema, CONF_NOTIFICATION_DEVICE_ID).default == "device-123"


def test_room_schema_uses_ha_selectors() -> None:
    """The room form should also be built with serializable selectors."""

    schema = build_room_schema({}, 0)
    schema_dict = schema.schema

    assert schema_dict[CONF_ROOM_TEMPERATURE_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_ROOM_HUMIDITY_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_ROOM_WEIGHT].__class__.__name__ == "All"


def test_room_schema_uses_numbered_default_name() -> None:
    """Room names should be numbered in a user-friendly way."""

    schema = build_room_schema({}, 1)

    assert _schema_entry(schema, CONF_ROOM_NAME).default == "Room 2"


def test_room_schema_honors_supplied_defaults() -> None:
    """Saved room values should be preserved in the edit form."""

    schema = build_room_schema(
        {
            CONF_ROOM_NAME: "Study",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.study_temp",
            CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.study_humidity",
            CONF_ROOM_WEIGHT: 2.5,
        },
        0,
    )

    assert _schema_entry(schema, CONF_ROOM_NAME).default == "Study"
    assert _schema_entry(schema, CONF_ROOM_TEMPERATURE_ENTITY_ID).default == "sensor.study_temp"
    assert _schema_entry(schema, CONF_ROOM_HUMIDITY_ENTITY_ID).default == "sensor.study_humidity"
    assert _schema_entry(schema, CONF_ROOM_WEIGHT).default == 2.5


def test_normalize_global_config_keeps_optional_entities_clean() -> None:
    """Optional entity and device fields should become None when empty."""

    data = normalize_global_config(
        {
            CONF_QUIET_HOURS_START: "22:00",
            CONF_QUIET_HOURS_END: "07:00:00",
            CONF_WIND_SPEED_ENTITY_ID: "",
            CONF_MASTER_CONTROL_ENTITY_ID: " ",
            CONF_NOTIFICATION_DEVICE_ID: None,
        }
    )

    assert data[CONF_QUIET_HOURS_START] == "22:00:00"
    assert data[CONF_QUIET_HOURS_END] == "07:00:00"
    assert data[CONF_WIND_SPEED_ENTITY_ID] is None
    assert data[CONF_MASTER_CONTROL_ENTITY_ID] is None
    assert data[CONF_NOTIFICATION_DEVICE_ID] is None


def test_normalize_global_config_preserves_seconds_precision() -> None:
    """Valid quiet-hours times with seconds should stay normalized."""

    data = normalize_global_config(
        {
            CONF_QUIET_HOURS_START: "22:15:30",
            CONF_QUIET_HOURS_END: "07:45:05",
        }
    )

    assert data[CONF_QUIET_HOURS_START] == "22:15:30"
    assert data[CONF_QUIET_HOURS_END] == "07:45:05"


def test_normalize_global_config_rejects_invalid_time_values() -> None:
    """Invalid quiet-hours inputs should fail before storage."""

    try:
        normalize_global_config(
            {
                CONF_QUIET_HOURS_START: "25:00",
                CONF_QUIET_HOURS_END: "07:00",
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid quiet-hours time to raise ValueError")


@pytest.mark.parametrize(
    "quiet_start,quiet_end",
    [
        ("7:00", "22:00"),
        ("07:00:00", "24:00:00"),
        ("night", "07:00"),
    ],
)
def test_normalize_global_config_rejects_bad_time_formats(quiet_start: str, quiet_end: str) -> None:
    """Bad quiet-hours formats should never be accepted."""

    with pytest.raises(ValueError):
        normalize_global_config(
            {
                CONF_QUIET_HOURS_START: quiet_start,
                CONF_QUIET_HOURS_END: quiet_end,
            }
        )


def test_normalize_room_config_strips_name_whitespace() -> None:
    """Room names should be stored without surrounding whitespace."""

    data = normalize_room_config(
        {
            CONF_ROOM_NAME: "  Bedroom  ",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temp",
            CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.bedroom_humidity",
            CONF_ROOM_WEIGHT: 1.25,
        }
    )

    assert data[CONF_ROOM_NAME] == "Bedroom"
    assert data[CONF_ROOM_WEIGHT] == 1.25


def test_split_config_data_separates_rooms_from_global_settings() -> None:
    """Persisted config should split cleanly into global and room settings."""

    global_data, rooms = split_config_data(
        {
            CONF_QUIET_HOURS_START: "22:00:00",
            CONF_QUIET_HOURS_END: "07:00:00",
            CONF_ROOM_NAME: "Ignored",
            "other": "value",
            "rooms": [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.living_humidity",
                }
            ],
        }
    )

    assert "rooms" not in global_data
    assert global_data["other"] == "value"
    assert rooms[0][CONF_ROOM_NAME] == "Living room"


def test_split_config_data_handles_missing_rooms_key() -> None:
    """The split helper should tolerate entries without room data."""

    global_data, rooms = split_config_data({CONF_QUIET_HOURS_START: "22:00:00"})

    assert global_data[CONF_QUIET_HOURS_START] == "22:00:00"
    assert rooms == []


def test_split_config_data_returns_copies_of_rooms() -> None:
    """Room dicts should be copied when splitting persisted config."""

    saved = {
        "rooms": [
            {
                CONF_ROOM_NAME: "Living room",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.living_humidity",
                CONF_ROOM_WEIGHT: 2.0,
            }
        ]
    }

    _, rooms = split_config_data(saved)
    saved["rooms"][0][CONF_ROOM_NAME] = "Mutated"

    assert rooms[0][CONF_ROOM_NAME] == "Living room"
