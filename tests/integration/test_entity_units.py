"""Regression tests for entity unit formatting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import UNIT_CELSIUS
from custom_components.ventwise.button import (
    VentWiseDebugCloseNotificationButton,
    VentWiseDebugOpenNotificationButton,
    VentWiseRequestRecommendationButton,
    _remove_debug_button_registry_entries,
)
from custom_components.ventwise.number import (
    ComfortTemperatureNumber,
    RoomTargetTemperatureOverrideNumber,
)
from custom_components.ventwise.sensor import (
    IndoorOutdoorHumidityDifferenceSensor,
    MoistureExchangeDirectionSensor,
    OutdoorAbsoluteHumiditySensor,
    OutdoorHumidityRatioSensor,
    OutdoorTemperatureSensor,
    OutdoorVaporPressureSensor,
    PerceivedComfortTemperatureSensor,
    PerceivedIndoorTemperatureSensor,
    PerceivedOutdoorTemperatureSensor,
    RoomIndoorTemperatureSensor,
    RoomIndoorAbsoluteHumiditySensor,
    RoomIndoorHumidityRatioSensor,
    RoomIndoorVaporPressureSensor,
    RoomPerceivedComfortTemperatureSensor,
    RoomPerceivedIndoorTemperatureSensor,
    RoomPerceivedOutdoorTemperatureSensor,
    RoomSuggestedComfortTemperatureSensor,
    RoomOutdoorTemperatureSensor,
    RoomOutdoorAbsoluteHumiditySensor,
    RoomOutdoorHumidityRatioSensor,
    RoomOutdoorVaporPressureSensor,
    SuggestedComfortTemperatureSensor,
)


def _coordinator() -> SimpleNamespace:
    return SimpleNamespace(
        config_entry=SimpleNamespace(entry_id="entry-1", title="VentWise"),
        config=SimpleNamespace(target_temperature_c=22.0, rooms=[]),
        hass=SimpleNamespace(config=SimpleNamespace(language="en")),
    )


def _room() -> SimpleNamespace:
    return SimpleNamespace(
        name="Camera",
        room_id=None,
        target_temperature_c_override=23.0,
        target_humidity_percent_override=55.0,
    )


def _coordinator_with_psychrometric_data() -> tuple[SimpleNamespace, SimpleNamespace]:
    room = _room()
    outdoor = SimpleNamespace(
        temperature_c=SimpleNamespace(value=20.0),
        humidity_percent=SimpleNamespace(value=50.0),
        pressure_hpa=SimpleNamespace(value=1013.25),
    )
    indoor = SimpleNamespace(
        room_id="Camera",
        temperature_c=SimpleNamespace(value=24.0),
        humidity_percent=SimpleNamespace(value=60.0),
    )
    coordinator = _coordinator()
    coordinator.config.rooms = [room]
    coordinator.data = SimpleNamespace(
        core_snapshot=SimpleNamespace(outdoor=outdoor, rooms=[indoor]),
        outdoor_temperature_c=20.0,
        outdoor_humidity_percent=50.0,
        outdoor_pressure_hpa=1013.25,
    )
    return coordinator, room


def test_celsius_sensor_units_are_consistent() -> None:
    coordinator = _coordinator()
    room = _room()

    assert UNIT_CELSIUS == "°C"
    sensors = [
        PerceivedIndoorTemperatureSensor(coordinator),
        PerceivedOutdoorTemperatureSensor(coordinator),
        PerceivedComfortTemperatureSensor(coordinator),
        SuggestedComfortTemperatureSensor(coordinator),
        OutdoorTemperatureSensor(coordinator),
        RoomPerceivedIndoorTemperatureSensor(coordinator, room),
        RoomPerceivedOutdoorTemperatureSensor(coordinator, room),
        RoomPerceivedComfortTemperatureSensor(coordinator, room),
        RoomSuggestedComfortTemperatureSensor(coordinator, room),
        RoomIndoorTemperatureSensor(coordinator, room),
        RoomOutdoorTemperatureSensor(coordinator, room),
    ]

    assert all(sensor.native_unit_of_measurement == UNIT_CELSIUS for sensor in sensors)


def test_celsius_number_units_are_consistent() -> None:
    coordinator = _coordinator()
    room = _room()

    numbers = [
        ComfortTemperatureNumber(coordinator),
        RoomTargetTemperatureOverrideNumber(coordinator, room),
    ]

    assert all(number.native_unit_of_measurement == UNIT_CELSIUS for number in numbers)


def test_on_demand_recommendation_button_has_a_stable_identity() -> None:
    button = VentWiseRequestRecommendationButton(_coordinator())

    assert button.unique_id == "entry-1_request_recommendation"
    assert button.translation_key == "request_recommendation"
    assert button.suggested_object_id == "request_recommendation"


def test_debug_room_buttons_have_stable_room_identities() -> None:
    coordinator = _coordinator()
    room = _room()
    room.room_id = "camera-1"

    open_button = VentWiseDebugOpenNotificationButton(coordinator, room)
    close_button = VentWiseDebugCloseNotificationButton(coordinator, room)

    assert open_button.unique_id == "entry-1_camera-1_debug_open_notification"
    assert close_button.unique_id == "entry-1_camera-1_debug_close_notification"
    assert open_button.translation_key == "debug_open_notification"
    assert close_button.translation_key == "debug_close_notification"
    assert open_button.suggested_object_id == "debug_open_notification"
    assert close_button.suggested_object_id == "debug_close_notification"


def test_suggested_object_id_does_not_follow_the_ui_language() -> None:
    """Localized labels must never make automations receive new entity IDs."""

    italian = _coordinator()
    italian.hass.config.language = "it"
    sensor = OutdoorTemperatureSensor(italian)

    assert sensor.translation_key == "outdoor_temperature"
    assert sensor.suggested_object_id == "outdoor_temperature"


def test_calculated_sensors_share_outdoor_values_on_global_and_room_devices() -> None:
    coordinator, room = _coordinator_with_psychrometric_data()

    outdoor_global = OutdoorAbsoluteHumiditySensor(coordinator)
    outdoor_room = RoomOutdoorAbsoluteHumiditySensor(coordinator, room)

    assert outdoor_global.native_value == pytest.approx(outdoor_room.native_value)
    assert outdoor_global.native_unit_of_measurement == "g/m³"
    assert outdoor_global.entity_category is None


def test_calculated_moisture_sensors_are_regular_entities() -> None:
    coordinator, room = _coordinator_with_psychrometric_data()

    sensors = [
        RoomIndoorAbsoluteHumiditySensor(coordinator, room),
        RoomIndoorHumidityRatioSensor(coordinator, room),
        RoomIndoorVaporPressureSensor(coordinator, room),
        RoomOutdoorHumidityRatioSensor(coordinator, room),
        RoomOutdoorVaporPressureSensor(coordinator, room),
        IndoorOutdoorHumidityDifferenceSensor(coordinator),
        MoistureExchangeDirectionSensor(coordinator),
    ]

    assert all(sensor.entity_category is None for sensor in sensors)
    assert sensors[0].native_value == pytest.approx(13.0, abs=0.2)
    assert sensors[1].native_value == pytest.approx(11.2, abs=0.3)
    assert sensors[2].native_value == pytest.approx(17.9, abs=0.2)
    assert sensors[-1].native_value == "drying"


def test_disabling_debug_mode_removes_only_debug_button_registry_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    removed: list[str] = []
    registry = SimpleNamespace(
        entities={
            "button.camera_open": SimpleNamespace(
                entity_id="button.camera_open",
                config_entry_id="entry-1",
                unique_id="entry-1_camera-1_debug_open_notification",
            ),
            "button.camera_close": SimpleNamespace(
                entity_id="button.camera_close",
                config_entry_id="entry-1",
                unique_id="entry-1_camera-1_debug_close_notification",
            ),
            "button.recommendation": SimpleNamespace(
                entity_id="button.recommendation",
                config_entry_id="entry-1",
                unique_id="entry-1_request_recommendation",
            ),
            "button.other": SimpleNamespace(
                entity_id="button.other",
                config_entry_id="other-entry",
                unique_id="other-entry_camera-1_debug_open_notification",
            ),
        },
        async_remove=removed.append,
    )
    from custom_components.ventwise import button as button_module

    monkeypatch.setattr(button_module.er, "async_get", lambda _hass: registry)

    _remove_debug_button_registry_entries(SimpleNamespace(), "entry-1")

    assert removed == ["button.camera_open", "button.camera_close"]
