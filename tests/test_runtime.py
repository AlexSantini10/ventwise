"""Tests for integration runtime helpers."""

from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

from custom_components.ventwise.const import (
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOMS,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_TEMPERATURE_C,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
)
from custom_components.ventwise.runtime import (
    build_integration_config,
    build_debug_attributes,
    build_room_profiles,
    dump_runtime_state,
    is_quiet_hours_active,
    load_runtime_state,
    state_to_bool,
    state_to_float,
)
from custom_components.ventwise.const import (
    CONF_RUNTIME_STATE,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
)
from custom_components.ventwise.runtime import RuntimeSnapshot
from ventwise_core import (
    ComfortObservation,
    ComfortRecommender,
    RecommendationContext,
    RoomObservation,
    RoomProfile,
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


def test_build_room_profiles_skips_missing_sensor_values() -> None:
    config = build_integration_config(
        {
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )

    rooms, outdoor = build_room_profiles(config, {}.get)

    assert outdoor is None
    assert rooms == []


def test_build_room_profiles_uses_neutral_humidity_when_outdoor_humidity_is_missing() -> None:
    config = build_integration_config(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                }
            ],
        }
    )

    fake_states = {
        "weather.home": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 20.0},
        ),
        "sensor.room_temp": SimpleNamespace(state="25.0"),
    }

    rooms, outdoor = build_room_profiles(config, fake_states.get)

    assert outdoor is not None
    assert outdoor.temperature_c == 20.0
    assert outdoor.humidity_percent == 50.0
    assert outdoor.wind_speed_m_s is None
    assert len(rooms) == 1


def test_build_room_profiles_falls_back_to_weather_state_without_attribute() -> None:
    config = build_integration_config(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                }
            ],
        }
    )

    fake_states = {
        "weather.home": SimpleNamespace(state="21.5", attributes={}),
        "sensor.room_temp": SimpleNamespace(state="25.0"),
    }

    rooms, outdoor = build_room_profiles(config, fake_states.get)

    assert outdoor is not None
    assert outdoor.temperature_c == 21.5
    assert outdoor.humidity_percent == 50.0
    assert outdoor.wind_speed_m_s is None
    assert rooms[0].name == "Camera"


def test_build_room_profiles_skips_unknown_room_temperature() -> None:
    config = build_integration_config(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )

    fake_states = {
        "weather.home": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 20.0, "humidity": 55.0},
        ),
        "sensor.room_temp": SimpleNamespace(state="unknown"),
        "sensor.room_humidity": SimpleNamespace(state="unavailable"),
    }

    rooms, outdoor = build_room_profiles(config, fake_states.get)

    assert outdoor is not None
    assert rooms == []


def test_build_debug_attributes_includes_summary_and_room_details() -> None:
    config = build_integration_config(
        {
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_SOFT_OUTDOOR_THRESHOLD_C: 22.0,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_STABILITY_MINUTES: 10,
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )
    recommender = ComfortRecommender()
    room_profiles = [
        RoomProfile(
            name="Camera",
            indoor=RoomObservation(temperature_c=26.0, humidity_percent=60.0),
        )
    ]
    outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)
    summary = recommender.evaluate(
        room_profiles,
        outdoor,
        RecommendationContext(stable_for_seconds=900),
    )
    snapshot = RuntimeSnapshot(
        summary=summary,
        notification_allowed=True,
        quiet_hours_active=False,
        cooldown_active=False,
        enabled=True,
        stable_for_seconds=900,
        last_updated=datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc),
    )

    attributes = build_debug_attributes(config, snapshot)

    assert attributes["summary_action"] == summary.action.value
    assert attributes["summary_best_room"] == "Camera"
    assert attributes["notification_allowed"] is True
    assert attributes["room_recommendations"][0]["room_name"] == "Camera"
    assert attributes["room_recommendations"][0]["indoor_perceived_c"] > 0
    assert attributes["best_room_recommendation"]["room_name"] == "Camera"


def test_runtime_state_round_trips_through_storage() -> None:
    started_at = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    notification_at = datetime(2026, 7, 21, 13, 5, tzinfo=timezone.utc)
    stored = dump_runtime_state(
        load_runtime_state(
            {
                CONF_RUNTIME_STATE: {
                    CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Camera"],
                    CONF_RUNTIME_LAST_ACTION_STARTED_AT: started_at.isoformat(),
                    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: ["open", "Camera"],
                    CONF_RUNTIME_LAST_NOTIFICATION_AT: notification_at.isoformat(),
                }
            }
        )
    )

    runtime_state = stored[CONF_RUNTIME_STATE]
    assert runtime_state[CONF_RUNTIME_LAST_ACTION_SIGNATURE] == ["open", "Camera"]
    assert runtime_state[CONF_RUNTIME_LAST_ACTION_STARTED_AT] == started_at.isoformat()
    assert runtime_state[CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE] == ["open", "Camera"]
    assert runtime_state[CONF_RUNTIME_LAST_NOTIFICATION_AT] == notification_at.isoformat()


def test_load_runtime_state_ignores_corrupted_markers() -> None:
    loaded = load_runtime_state(
        {
            CONF_RUNTIME_STATE: {
                CONF_RUNTIME_LAST_ACTION_SIGNATURE: "invalid",
                CONF_RUNTIME_LAST_ACTION_STARTED_AT: "not-a-timestamp",
                CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-07-21T13:05:00+00:00",
            }
        }
    )

    assert loaded.last_action_signature is None
    assert loaded.last_action_started_at is None
    assert loaded.last_notification_signature == ("open", "Camera")
    assert loaded.last_notification_at == datetime(2026, 7, 21, 13, 5, tzinfo=timezone.utc)
