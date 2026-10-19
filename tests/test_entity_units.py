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
    OutdoorTemperatureSensor,
    PerceivedComfortTemperatureSensor,
    PerceivedIndoorTemperatureSensor,
    PerceivedOutdoorTemperatureSensor,
    RoomIndoorTemperatureSensor,
    RoomPerceivedComfortTemperatureSensor,
    RoomPerceivedIndoorTemperatureSensor,
    RoomPerceivedOutdoorTemperatureSensor,
    RoomSuggestedComfortTemperatureSensor,
    RoomOutdoorTemperatureSensor,
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
    assert button.name == "Request recommendation now"


def test_debug_room_buttons_have_stable_room_identities() -> None:
    coordinator = _coordinator()
    room = _room()
    room.room_id = "camera-1"

    open_button = VentWiseDebugOpenNotificationButton(coordinator, room)
    close_button = VentWiseDebugCloseNotificationButton(coordinator, room)

    assert open_button.unique_id == "entry-1_camera-1_debug_open_notification"
    assert close_button.unique_id == "entry-1_camera-1_debug_close_notification"
    assert open_button.name == "Receive open notification"
    assert close_button.name == "Receive close notification"


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
