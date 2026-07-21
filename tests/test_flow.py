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


def test_room_schema_uses_ha_selectors() -> None:
    """The room form should also be built with serializable selectors."""

    schema = build_room_schema({}, 0)
    schema_dict = schema.schema

    assert schema_dict[CONF_ROOM_TEMPERATURE_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_ROOM_HUMIDITY_ENTITY_ID].__class__.__name__ == "EntitySelector"
    assert schema_dict[CONF_ROOM_WEIGHT].__class__.__name__ == "All"


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
