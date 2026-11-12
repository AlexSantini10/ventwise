"""Unit conversion at the VentWise integration boundary."""

from __future__ import annotations

from .const import (
    DEFAULT_TEMPERATURE_UNIT, DEFAULT_WIND_SPEED_UNIT, UNIT_CELSIUS,
    UNIT_FAHRENHEIT, UNIT_KILOMETERS_PER_HOUR, UNIT_KNOTS,
    UNIT_METERS_PER_SECOND, UNIT_MILES_PER_HOUR,
)

TEMPERATURE_UNITS = (UNIT_CELSIUS, UNIT_FAHRENHEIT)
WIND_SPEED_UNITS = (UNIT_METERS_PER_SECOND, UNIT_KILOMETERS_PER_HOUR, UNIT_MILES_PER_HOUR, UNIT_KNOTS)
HUMIDITY_UNITS = ("%",)
CO2_UNITS = ("ppm",)
DISPLAY_PRECISION = 2


def temperature_unit(value: object) -> str:
    return str(value) if value in TEMPERATURE_UNITS else DEFAULT_TEMPERATURE_UNIT


def wind_speed_unit(value: object) -> str:
    return str(value) if value in WIND_SPEED_UNITS else DEFAULT_WIND_SPEED_UNIT


def source_unit(value: object, measurement: str) -> str | None:
    """Normalize a user-declared native source unit without guessing."""

    choices = {
        "temperature": TEMPERATURE_UNITS,
        "humidity": HUMIDITY_UNITS,
        "wind_speed": WIND_SPEED_UNITS,
        "co2": CO2_UNITS,
    }.get(measurement)
    if choices is None or value not in choices:
        return None
    return str(value)


def source_unit_from_state(state, configured: str | None, measurement: str) -> str | None:
    """Return a validated source unit, rejecting native/configured conflicts."""

    declared = source_unit(configured, measurement)
    attributes = getattr(state, "attributes", {}) or {}
    native = attributes.get("unit_of_measurement")
    if native is None and measurement == "temperature":
        native = attributes.get("temperature_unit")
    if native is None and measurement == "wind_speed":
        native = attributes.get("wind_speed_unit")
    if native is None:
        return declared or {
            "temperature": UNIT_CELSIUS,
            "humidity": "%",
            "wind_speed": UNIT_METERS_PER_SECOND,
            "co2": "ppm",
        }.get(measurement)
    native = source_unit(native, measurement)
    if native is None:
        return None
    if declared is None:
        return native
    if native != declared:
        return None
    return native


def source_value_to_canonical(value: float, state, configured: str | None, measurement: str) -> float | None:
    """Validate a configured source unit and convert into engine units."""

    unit = source_unit_from_state(state, configured, measurement)
    if unit is None:
        return None
    if measurement == "temperature":
        return temperature_to_celsius(value, unit)
    if measurement == "wind_speed":
        return wind_speed_to_m_s(value, unit)
    return value


def temperature_to_celsius(value: float, unit: object) -> float:
    return (value - 32) * 5 / 9 if temperature_unit(unit) == UNIT_FAHRENHEIT else value


def temperature_from_celsius(value: float | None, unit: object) -> float | None:
    if value is None:
        return None
    return value * 9 / 5 + 32 if temperature_unit(unit) == UNIT_FAHRENHEIT else value


def wind_speed_to_m_s(value: float, unit: object) -> float:
    unit = wind_speed_unit(unit)
    if unit == UNIT_KILOMETERS_PER_HOUR:
        return value / 3.6
    if unit == UNIT_MILES_PER_HOUR:
        return value * 0.44704
    if unit == UNIT_KNOTS:
        return value * 0.514444
    return value


def wind_speed_from_m_s(value: float | None, unit: object) -> float | None:
    if value is None:
        return None
    unit = wind_speed_unit(unit)
    if unit == UNIT_KILOMETERS_PER_HOUR:
        return value * 3.6
    if unit == UNIT_MILES_PER_HOUR:
        return value / 0.44704
    if unit == UNIT_KNOTS:
        return value / 0.514444
    return value


def state_unit(state, fallback: str, measurement: str | None = None) -> str:
    """Read Home Assistant's declared source unit, preserving legacy fallback."""
    attributes = getattr(state, "attributes", {}) or {}
    if measurement == "temperature":
        return attributes.get("unit_of_measurement") or attributes.get("temperature_unit") or fallback
    if measurement == "wind_speed":
        return attributes.get("unit_of_measurement") or attributes.get("wind_speed_unit") or fallback
    return attributes.get("unit_of_measurement") or fallback


def display_value(value: float | None) -> float | None:
    """Round a user-facing measurement without affecting canonical values."""
    return round(value, DISPLAY_PRECISION) if value is not None else None
