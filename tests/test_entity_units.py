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

    assert UNIT_CELSIUS == "degC"
    assert PerceivedIndoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert PerceivedOutdoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert PerceivedComfortTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert SuggestedComfortTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert OutdoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomPerceivedIndoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomPerceivedOutdoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomPerceivedComfortTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomSuggestedComfortTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomIndoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomOutdoorTemperatureSensor._attr_native_unit_of_measurement == UNIT_CELSIUS

    assert PerceivedIndoorTemperatureSensor(coordinator)._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert SuggestedComfortTemperatureSensor(coordinator)._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomIndoorTemperatureSensor(coordinator, room)._attr_native_unit_of_measurement == UNIT_CELSIUS


def test_celsius_number_units_are_consistent() -> None:
    coordinator = _coordinator()
    room = _room()

    assert ComfortTemperatureNumber._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomTargetTemperatureOverrideNumber._attr_native_unit_of_measurement == UNIT_CELSIUS

    assert ComfortTemperatureNumber(coordinator)._attr_native_unit_of_measurement == UNIT_CELSIUS
    assert RoomTargetTemperatureOverrideNumber(coordinator, room)._attr_native_unit_of_measurement == UNIT_CELSIUS
