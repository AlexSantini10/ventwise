"""Unit conversion coverage for the VentWise boundary."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from custom_components.ventwise.const import (
    UNIT_CELSIUS, UNIT_FAHRENHEIT, UNIT_KILOMETERS_PER_HOUR, UNIT_KNOTS,
    UNIT_METERS_PER_SECOND, UNIT_MILES_PER_HOUR,
)
from custom_components.ventwise.units import (
    normalize_measurement,
    temperature_from_celsius, temperature_to_celsius,
    display_value, wind_speed_from_m_s, wind_speed_to_m_s,
)
from custom_components.ventwise.application.runtime.integration_runtime import state_to_temperature_c


def test_temperature_conversion_round_trip() -> None:
    assert temperature_from_celsius(20.0, UNIT_FAHRENHEIT) == pytest.approx(68.0)
    assert temperature_to_celsius(68.0, UNIT_FAHRENHEIT) == pytest.approx(20.0)
    assert temperature_to_celsius(20.0, UNIT_CELSIUS) == 20.0


@pytest.mark.parametrize(
    ("unit", "value"),
    ((UNIT_METERS_PER_SECOND, 10.0), (UNIT_KILOMETERS_PER_HOUR, 36.0), (UNIT_MILES_PER_HOUR, 22.3694), (UNIT_KNOTS, 19.4385)),
)
def test_wind_speed_conversion_round_trip(unit: str, value: float) -> None:
    canonical = wind_speed_to_m_s(value, unit)
    assert canonical == pytest.approx(10.0, abs=0.001)
    assert wind_speed_from_m_s(canonical, unit) == pytest.approx(value, abs=0.001)


def test_home_assistant_temperature_source_uses_declared_unit() -> None:
    state = SimpleNamespace(state="68", attributes={"unit_of_measurement": UNIT_FAHRENHEIT})
    assert state_to_temperature_c(state) == pytest.approx(20.0)


def test_home_assistant_temperature_source_converts_kelvin() -> None:
    state = SimpleNamespace(state="293.15", attributes={"unit_of_measurement": "K"})
    assert state_to_temperature_c(state) == pytest.approx(20.0)


def test_home_assistant_temperature_source_rejects_unknown_unit() -> None:
    state = SimpleNamespace(state="20", attributes={"unit_of_measurement": "rankine"})
    assert state_to_temperature_c(state) is None


def test_display_values_are_limited_to_two_decimal_places() -> None:
    assert display_value(4.4738725841088) == 4.47


@pytest.mark.parametrize(
    ("measurement", "value", "unit", "expected"),
    (("temperature", 32.0, UNIT_FAHRENHEIT, 0.0), ("temperature", 273.15, "K", 0.0),
     ("humidity", 0.5, "ratio", 50.0), ("wind_speed", 36.0, UNIT_KILOMETERS_PER_HOUR, 10.0),
     ("pressure", 1.0, "bar", 1000.0)),
)
def test_boundary_normalization_uses_canonical_units(measurement, value, unit, expected) -> None:
    normalized, _, reason = normalize_measurement(value, unit, measurement)
    assert normalized == pytest.approx(expected)
    assert reason is None


@pytest.mark.parametrize("value", ("not-a-number", float("nan"), float("inf")))
def test_boundary_normalization_rejects_non_finite_or_non_numeric_values(value) -> None:
    normalized, _, reason = normalize_measurement(value, "%", "humidity")
    assert normalized is None
    assert reason in {"non_numeric", "non_finite"}


def test_boundary_normalization_rejects_unknown_units() -> None:
    normalized, _, reason = normalize_measurement(20.0, "rankine", "temperature")
    assert normalized is None
    assert reason == "unknown_unit"
