"""Pure psychrometric calculations used by the decision pipeline."""

from __future__ import annotations

from math import exp


def saturation_vapor_pressure_hpa(temperature_c: float) -> float:
    """Return saturation vapor pressure in hPa using the Magnus formula."""

    _check_temperature(temperature_c)
    return 6.112 * exp((17.62 * temperature_c) / (243.12 + temperature_c))


def vapor_pressure_hpa(temperature_c: float, relative_humidity_percent: float) -> float:
    """Return water vapor partial pressure in hPa."""

    _check_humidity(relative_humidity_percent)
    return saturation_vapor_pressure_hpa(temperature_c) * relative_humidity_percent / 100.0


def absolute_humidity_g_m3(temperature_c: float, relative_humidity_percent: float) -> float:
    """Return water vapor mass per cubic meter of air."""

    return 216.7 * vapor_pressure_hpa(temperature_c, relative_humidity_percent) / (temperature_c + 273.15)


def humidity_ratio_g_kg(temperature_c: float, relative_humidity_percent: float, pressure_hpa: float = 1013.25) -> float:
    """Return humidity ratio in grams of water per kilogram of dry air."""

    if pressure_hpa <= 0:
        raise ValueError("pressure_hpa must be positive")
    vapor_pressure = vapor_pressure_hpa(temperature_c, relative_humidity_percent)
    if vapor_pressure >= pressure_hpa:
        raise ValueError("vapor pressure must be lower than total pressure")
    return 621.945 * vapor_pressure / (pressure_hpa - vapor_pressure)


def relative_humidity_percent_from_absolute(
    temperature_c: float,
    absolute_humidity_g_m3: float,
) -> float:
    """Reconstruct RH from absolute humidity at the specified temperature."""

    _check_temperature(temperature_c)
    if not 0.0 <= absolute_humidity_g_m3:
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
    if not -80.0 <= temperature_c <= 70.0:
        raise ValueError("temperature_c is outside the supported domain")


def _check_humidity(relative_humidity_percent: float) -> None:
    if not 0.0 <= relative_humidity_percent <= 100.0:
        raise ValueError("relative_humidity_percent must be between 0 and 100")
