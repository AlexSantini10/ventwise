"""Tests for integration runtime helpers."""

from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime

from custom_components.temperature_comfort_recommender.const import (
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOMS,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WEIGHT,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_TEMPERATURE_C,
)
from custom_components.temperature_comfort_recommender.runtime import (
    build_integration_config,
    build_room_profiles,
    is_quiet_hours_active,
    state_to_bool,
    state_to_float,
)


def test_state_helpers_parse_values() -> None:
    assert state_to_float(SimpleNamespace(state="21.5")) == 21.5
    assert state_to_float(SimpleNamespace(state="unknown")) is None
    assert state_to_float(SimpleNamespace(state="not-a-number")) is None
    assert state_to_bool(SimpleNamespace(state="on")) is True
    assert state_to_bool(SimpleNamespace(state="off")) is False
    assert state_to_bool(SimpleNamespace(state="1")) is True
    assert state_to_bool(SimpleNamespace(state="0")) is False


def test_quiet_hours_support_wraparound_midnight() -> None:
    now = datetime(2026, 7, 20, 1, 30, 0)

    assert is_quiet_hours_active(now, "22:00:00", "07:00:00") is True
    assert is_quiet_hours_active(now, "08:00:00", "21:00:00") is False


def test_build_runtime_config_and_room_profiles() -> None:
    config = build_integration_config(
        {
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_STABILITY_MINUTES: 10,
            CONF_QUIET_HOURS_ENABLED: True,
            CONF_QUIET_HOURS_START: "22:00:00",
            CONF_QUIET_HOURS_END: "07:00:00",
            CONF_ENABLED: True,
            CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "sensor.outdoor_temp",
            CONF_OUTDOOR_HUMIDITY_ENTITY_ID: "sensor.outdoor_humidity",
            CONF_NOTIFICATION_DEVICE_ID: "device-123",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                    CONF_ROOM_WEIGHT: 1.5,
                }
            ],
        }
    )

    assert config.enabled is True
    assert config.notification_device_id == "device-123"
    assert config.rooms[0].name == "Camera"

    fake_states = {
        "sensor.outdoor_temp": SimpleNamespace(state="20.0"),
        "sensor.outdoor_humidity": SimpleNamespace(state="55"),
        "sensor.room_temp": SimpleNamespace(state="26.0"),
        "sensor.room_humidity": SimpleNamespace(state="60"),
    }

    rooms, outdoor = build_room_profiles(config, fake_states.get)

    assert outdoor is not None
    assert outdoor.temperature_c == 20.0
    assert len(rooms) == 1
    assert rooms[0].name == "Camera"
    assert rooms[0].weight == 1.5


def test_build_room_profiles_skips_missing_sensor_values() -> None:
    config = build_integration_config(
        {
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                    CONF_ROOM_WEIGHT: 1.0,
                }
            ],
        }
    )

    rooms, outdoor = build_room_profiles(config, {}.get)

    assert outdoor is None
    assert rooms == []
