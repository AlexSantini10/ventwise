"""Pure psychrometric calculations used by the decision pipeline."""

from __future__ import annotations

from math import exp, isfinite


DEFAULT_PRESSURE_HPA = 1013.25


def saturation_vapor_pressure_hpa(temperature_c: float) -> float:
    """Return saturation vapor pressure in hPa using the Magnus formula."""

    _check_temperature(temperature_c)
    return 6.112 * exp((17.62 * temperature_c) / (243.12 + temperature_c))


def vapor_pressure_hpa(temperature_c: float, relative_humidity_percent: float) -> float:
    """Return water vapor partial pressure in hPa."""

    _check_humidity(relative_humidity_percent)
    return saturation_vapor_pressure_hpa(temperature_c) * relative_humidity_percent / 100.0


def perceived_temperature_c(
    temperature_c: float,
    relative_humidity_percent: float | None,
    target_temperature_c: float,
    target_humidity_percent: float,
) -> float:
    """Estimate comfort temperature using vapor-pressure deviation.

    The result is a deliberately modest comfort heuristic, not a certified
    heat-index or PMV calculation. Vapor pressure is used instead of a raw RH
    difference so equal RH values at different temperatures are not treated
    as equal moisture loads.
    """

    if relative_humidity_percent is None:
        return temperature_c
    humidity_effect_c = (
        vapor_pressure_hpa(temperature_c, relative_humidity_percent)
        - vapor_pressure_hpa(target_temperature_c, target_humidity_percent)
    ) * 0.08
    return temperature_c + max(-3.0, min(3.0, humidity_effect_c))


def absolute_humidity_g_m3(temperature_c: float, relative_humidity_percent: float) -> float:
    """Return water vapor mass per cubic meter of air."""

    return 216.7 * vapor_pressure_hpa(temperature_c, relative_humidity_percent) / (temperature_c + 273.15)


def humidity_ratio_g_kg(
    temperature_c: float,
    relative_humidity_percent: float,
    pressure_hpa: float = DEFAULT_PRESSURE_HPA,
) -> float:
    """Return humidity ratio in grams of water per kilogram of dry air."""

    if not isfinite(pressure_hpa) or pressure_hpa <= 0:
        raise ValueError("pressure_hpa must be positive")
    vapor_pressure = vapor_pressure_hpa(temperature_c, relative_humidity_percent)
    if vapor_pressure >= pressure_hpa:
        raise ValueError("vapor pressure must be lower than total pressure")
    return 621.945 * vapor_pressure / (pressure_hpa - vapor_pressure)


def relative_humidity_percent_from_humidity_ratio(
    temperature_c: float,
    humidity_ratio_g_kg_value: float,
    pressure_hpa: float = DEFAULT_PRESSURE_HPA,
) -> float:
    """Reconstruct RH from humidity ratio at an explicit total pressure.

    The result is deliberately not clipped: a value above 100% represents a
    supersaturated model state and must remain visible to the caller.
    """

    _check_temperature(temperature_c)
    if not isfinite(humidity_ratio_g_kg_value) or humidity_ratio_g_kg_value < 0:
        raise ValueError("humidity_ratio_g_kg_value must be non-negative")
    _check_pressure(pressure_hpa)
    vapor_pressure = pressure_hpa * humidity_ratio_g_kg_value / (621.945 + humidity_ratio_g_kg_value)
    return 100.0 * vapor_pressure / saturation_vapor_pressure_hpa(temperature_c)


def humidity_ratio_g_kg_from_relative_humidity(
    temperature_c: float,
    relative_humidity_percent: float,
    pressure_hpa: float = DEFAULT_PRESSURE_HPA,
) -> float:
    """Named inverse companion for callers that prefer the source-first API."""

    return humidity_ratio_g_kg(temperature_c, relative_humidity_percent, pressure_hpa)


def pressure_hpa_or_default(pressure_hpa: float | None) -> tuple[float, bool]:
    """Return pressure and whether the documented barometric fallback was used."""

    if pressure_hpa is None:
        return DEFAULT_PRESSURE_HPA, True
    _check_pressure(pressure_hpa)
    return pressure_hpa, False


def relative_humidity_percent_from_absolute(
    temperature_c: float,
    absolute_humidity_g_m3: float,
) -> float:
    """Reconstruct RH from absolute humidity at the specified temperature."""

    _check_temperature(temperature_c)
    if not isfinite(absolute_humidity_g_m3) or not 0.0 <= absolute_humidity_g_m3:
        raise ValueError("absolute_humidity_g_m3 must be non-negative")
    rh = absolute_humidity_g_m3 * (temperature_c + 273.15) / (
        216.7 * saturation_vapor_pressure_hpa(temperature_c)
    ) * 100.0
    return max(0.0, min(100.0, rh))


def moisture_exchange_direction(indoor_absolute_humidity_g_m3: float, outdoor_absolute_humidity_g_m3: float) -> str:
    """Describe whether incoming outdoor air is drying, humidifying, or neutral."""

    delta = outdoor_absolute_humidity_g_m3 - indoor_absolute_humidity_g_m3
    if delta < -0.1:
        return "drying"
    if delta > 0.1:
        return "humidifying"
    return "neutral"


def _check_temperature(temperature_c: float) -> None:
    if not isfinite(temperature_c) or not -80.0 <= temperature_c <= 70.0:
        raise ValueError("temperature_c is outside the supported domain")


def _check_humidity(relative_humidity_percent: float) -> None:
    if not isfinite(relative_humidity_percent) or not 0.0 <= relative_humidity_percent <= 100.0:
        raise ValueError("relative_humidity_percent must be between 0 and 100")


def _check_pressure(pressure_hpa: float) -> None:
    if not isfinite(pressure_hpa) or pressure_hpa <= 0:
        raise ValueError("pressure_hpa must be positive")
