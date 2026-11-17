"""Reference and boundary tests for psychrometric calculations."""

import pytest

from ventwise_core import (
    absolute_humidity_g_m3,
    humidity_ratio_g_kg,
    moisture_exchange_direction,
    relative_humidity_percent_from_absolute,
    saturation_vapor_pressure_hpa,
)


def test_saturation_pressure_at_twenty_celsius_matches_reference():
    assert saturation_vapor_pressure_hpa(20.0) == pytest.approx(23.37, abs=0.05)


def test_absolute_humidity_round_trip():
    absolute = absolute_humidity_g_m3(20.0, 50.0)
    assert absolute == pytest.approx(8.64, abs=0.1)
    assert relative_humidity_percent_from_absolute(20.0, absolute) == pytest.approx(50.0, abs=0.1)


def test_humidity_ratio_is_dimensionally_distinct_from_absolute_humidity():
    assert humidity_ratio_g_kg(20.0, 50.0) == pytest.approx(7.3, abs=0.2)


def test_moisture_direction_uses_water_content_not_rh_alone():
    assert moisture_exchange_direction(12.0, 8.0) == "drying"
    assert moisture_exchange_direction(8.0, 12.0) == "humidifying"
    assert moisture_exchange_direction(8.0, 8.05) == "neutral"


@pytest.mark.parametrize(
    ("temperature", "humidity"),
    [(20.0, -1.0), (20.0, 101.0), (-81.0, 50.0)],
)
def test_invalid_domains_are_rejected(temperature, humidity):
    with pytest.raises(ValueError):
        absolute_humidity_g_m3(temperature, humidity)
