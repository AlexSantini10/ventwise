"""Opt-in Open-Meteo/CAMS air-quality adapter.

Coordinates are read from Home Assistant only for the request and are never
stored in the config entry, runtime state, trace, or logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Mapping

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from ..const import AIR_QUALITY_VARIABLES
from ..ventwise_core import Observation

_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_ATTRIBUTION = "Open-Meteo / CAMS"
_LOGGER = logging.getLogger(__name__)


class ProviderUnavailableError(RuntimeError):
    """An optional provider could not produce a usable response."""


@dataclass(frozen=True, slots=True)
class ProviderExposure:
    """A current provider reading plus its model metadata."""

    observation: Observation[float]
    averaging_period: str = "instant"
    attribution: str = _ATTRIBUTION
    resolution: str = "~11 km"
    coverage: str = "model forecast; pollen Europe/season only"


async def async_fetch_open_meteo_exposure(hass, now: datetime) -> Mapping[str, ProviderExposure]:
    """Fetch the current model values using HA's configured location in memory."""

    latitude = getattr(hass.config, "latitude", None)
    longitude = getattr(hass.config, "longitude", None)
    if latitude is None or longitude is None:
        return {}
    session = async_get_clientsession(hass)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(AIR_QUALITY_VARIABLES),
        "timezone": "UTC",
    }
    try:
        async with session.get(_URL, params=params, timeout=10) as response:
            response.raise_for_status()
            payload = await response.json()
    except Exception as err:
        # This is an expected optional-source failure: keep the decision engine
        # fail-closed, but provide a visible classified state to the coordinator.
        _LOGGER.warning("VentWise optional air-quality provider is unavailable: %s", type(err).__name__)
        raise ProviderUnavailableError from None
    if not isinstance(payload, dict):
        _LOGGER.warning("VentWise optional air-quality provider returned invalid data")
        raise ProviderUnavailableError
    current = payload.get("current")
    units = payload.get("current_units")
    if not isinstance(current, Mapping) or not isinstance(units, Mapping):
        _LOGGER.warning("VentWise optional air-quality provider returned invalid current data")
        raise ProviderUnavailableError
    observed_at = _parse_time(current.get("time")) or now
    result: dict[str, ProviderExposure] = {}
    for key in AIR_QUALITY_VARIABLES:
        value = current.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        result[key] = ProviderExposure(
            Observation(numeric, str(units.get(key, "")), observed_at, now, "open_meteo_cams")
        )
    if not result:
        _LOGGER.warning("VentWise optional air-quality provider returned no usable current values")
        raise ProviderUnavailableError
    return result


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt_util.as_utc(parsed) if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
