"""Reference and boundary tests for psychrometric calculations."""

import pytest

from ventwise_core import (
    DEFAULT_PRESSURE_HPA,
    absolute_humidity_g_m3,
    humidity_ratio_g_kg,
    moisture_exchange_direction,
    relative_humidity_percent_from_absolute,
    relative_humidity_percent_from_humidity_ratio,
    pressure_hpa_or_default,
    perceived_temperature_c,
    saturation_vapor_pressure_hpa,
)


def test_perceived_temperature_uses_vapor_pressure_not_raw_rh_delta():
    warm_effect = perceived_temperature_c(30.0, 60.0, 22.0, 50.0) - 30.0
    cool_effect = perceived_temperature_c(15.0, 60.0, 22.0, 50.0) - 15.0
    assert warm_effect > cool_effect


def test_saturation_pressure_at_twenty_celsius_matches_reference():
    assert saturation_vapor_pressure_hpa(20.0) == pytest.approx(23.37, abs=0.05)


def test_absolute_humidity_round_trip():
    absolute = absolute_humidity_g_m3(20.0, 50.0)
    assert absolute == pytest.approx(8.64, abs=0.1)
    assert relative_humidity_percent_from_absolute(20.0, absolute) == pytest.approx(50.0, abs=0.1)


def test_humidity_ratio_is_dimensionally_distinct_from_absolute_humidity():
    assert humidity_ratio_g_kg(20.0, 50.0) == pytest.approx(7.3, abs=0.2)


def test_humidity_ratio_round_trip_uses_explicit_pressure():
    ratio = humidity_ratio_g_kg(20.0, 50.0, 1000.0)
    assert relative_humidity_percent_from_humidity_ratio(20.0, ratio, 1000.0) == pytest.approx(50.0)


def test_pressure_fallback_is_explicitly_estimated():
    assert pressure_hpa_or_default(None) == (DEFAULT_PRESSURE_HPA, True)
    assert pressure_hpa_or_default(1000.0) == (1000.0, False)
    with pytest.raises(ValueError):
        pressure_hpa_or_default(float("nan"))


def test_supersaturated_inverse_result_is_not_silently_clipped():
    ratio_at_saturation = humidity_ratio_g_kg(20.0, 100.0)
    reconstructed = relative_humidity_percent_from_humidity_ratio(15.0, ratio_at_saturation)
    assert reconstructed > 100.0


def test_inverse_rejects_non_physical_ratio_and_pressure():
    with pytest.raises(ValueError):
        relative_humidity_percent_from_humidity_ratio(20.0, -1.0)
    with pytest.raises(ValueError):
        relative_humidity_percent_from_humidity_ratio(20.0, 7.0, 0.0)


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
