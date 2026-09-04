"""Regression tests for entity unit formatting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import UNIT_CELSIUS
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
