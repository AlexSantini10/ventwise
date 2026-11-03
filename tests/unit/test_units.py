"""Unit conversion coverage for the VentWise boundary."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from custom_components.ventwise.const import (
    UNIT_CELSIUS, UNIT_FAHRENHEIT, UNIT_KILOMETERS_PER_HOUR, UNIT_KNOTS,
    UNIT_METERS_PER_SECOND, UNIT_MILES_PER_HOUR,
)
from custom_components.ventwise.units import (
    temperature_from_celsius, temperature_to_celsius,
    wind_speed_from_m_s, wind_speed_to_m_s,
)
from custom_components.ventwise.application.runtime import state_to_temperature_c


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
