"""Unit conversion at the VentWise integration boundary."""

from __future__ import annotations

from math import isfinite

from .const import (
    DEFAULT_TEMPERATURE_UNIT, DEFAULT_WIND_SPEED_UNIT, UNIT_CELSIUS,
    UNIT_FAHRENHEIT, UNIT_KELVIN, UNIT_KILOMETERS_PER_HOUR, UNIT_KNOTS,
    UNIT_METERS_PER_SECOND, UNIT_MILES_PER_HOUR,
)

TEMPERATURE_UNITS = (UNIT_CELSIUS, UNIT_FAHRENHEIT, UNIT_KELVIN)
HUMIDITY_UNITS = ("%", "ratio")
WIND_SPEED_UNITS = (UNIT_METERS_PER_SECOND, UNIT_KILOMETERS_PER_HOUR, UNIT_MILES_PER_HOUR, UNIT_KNOTS)
PRESSURE_UNITS = ("hPa", "Pa", "kPa", "bar", "atm", "psi", "inHg")
DISPLAY_PRECISION = 2

_UNIT_ALIASES = {
    "temperature": {"°c": UNIT_CELSIUS, "c": UNIT_CELSIUS, "celsius": UNIT_CELSIUS,
                    "°f": UNIT_FAHRENHEIT, "f": UNIT_FAHRENHEIT, "fahrenheit": UNIT_FAHRENHEIT,
                    "k": UNIT_KELVIN, "kelvin": UNIT_KELVIN},
    "humidity": {"%": "%", "percent": "%", "percentage": "%", "ratio": "ratio", "fraction": "ratio"},
    "wind_speed": {"m/s": UNIT_METERS_PER_SECOND, "mps": UNIT_METERS_PER_SECOND,
                   "km/h": UNIT_KILOMETERS_PER_HOUR, "kph": UNIT_KILOMETERS_PER_HOUR,
                   "mph": UNIT_MILES_PER_HOUR, "kn": UNIT_KNOTS, "knot": UNIT_KNOTS, "knots": UNIT_KNOTS},
    "pressure": {unit.lower(): unit for unit in PRESSURE_UNITS},
    "co2": {"ppm": "ppm", "parts per million": "ppm"},
}


def canonical_unit(measurement: str, unit: object) -> str:
    """Return a supported declared unit or reject ambiguous metadata."""
    key = str(unit).strip().lower() if unit is not None else ""
    try:
        return _UNIT_ALIASES[measurement][key]
    except KeyError as exc:
        raise ValueError(f"unsupported {measurement} unit: {unit!r}") from exc


def canonical_unit_name(measurement: str) -> str:
    return {"temperature": UNIT_CELSIUS, "humidity": "%", "wind_speed": UNIT_METERS_PER_SECOND, "pressure": "hPa", "co2": "ppm"}[measurement]


def normalize_measurement(value: object, unit: object, measurement: str) -> tuple[float | None, str, str | None]:
    """Normalize a declared measurement and return value, canonical unit, and reason."""
    try:
        numeric = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None, canonical_unit_name(measurement), "non_numeric"
    try:
        source_unit = canonical_unit(measurement, unit)
    except ValueError:
        return None, canonical_unit_name(measurement), "unknown_unit"
    if numeric is None:
        return None, canonical_unit_name(measurement), "missing"
    if not isfinite(numeric):
        return None, canonical_unit_name(measurement), "non_finite"
    if measurement == "temperature":
        result = numeric - 273.15 if source_unit == UNIT_KELVIN else temperature_to_celsius(numeric, source_unit)
    elif measurement == "humidity":
        result = numeric * 100.0 if source_unit == "ratio" else numeric
    elif measurement == "wind_speed":
        result = wind_speed_to_m_s(numeric, source_unit)
    elif measurement == "pressure":
        factors = {"hPa": 1.0, "Pa": 0.01, "kPa": 10.0, "bar": 1000.0, "atm": 1013.25, "psi": 68.9475729, "inHg": 33.8638867}
        result = numeric * factors[source_unit]
    elif measurement == "co2":
        result = numeric
    else:
        raise ValueError(f"unsupported measurement: {measurement}")
    return result, canonical_unit_name(measurement), None


def temperature_unit(value: object) -> str:
    return str(value) if value in TEMPERATURE_UNITS else DEFAULT_TEMPERATURE_UNIT


def wind_speed_unit(value: object) -> str:
    return str(value) if value in WIND_SPEED_UNITS else DEFAULT_WIND_SPEED_UNIT


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
