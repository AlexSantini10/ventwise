"""Temperature Comfort Recommender integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import DOMAIN, NAME

try:  # Home Assistant is not installed in the unit-test environment.
    from homeassistant.const import Platform
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import TemperatureComfortRecommenderCoordinator

    PLATFORMS: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
        Platform.SWITCH,
    ]
    HA_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - test-time fallback
    ConfigEntry = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]
    TemperatureComfortRecommenderCoordinator = Any  # type: ignore[assignment]
    PLATFORMS: list[Any] = []
    HA_AVAILABLE = False


@dataclass(slots=True)
class IntegrationRuntimeData:
    """Runtime storage for the integration."""

    coordinator: TemperatureComfortRecommenderCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    if not HA_AVAILABLE:  # pragma: no cover - safety net for local imports
        return True

    coordinator = TemperatureComfortRecommenderCoordinator(
        hass,
        entry,
        {**entry.data, **entry.options},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IntegrationRuntimeData(
        coordinator=coordinator
    )
    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if not HA_AVAILABLE:  # pragma: no cover - safety net for local imports
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when config entry options change."""

    if not HA_AVAILABLE:  # pragma: no cover - safety net for local imports
        return None

    await hass.config_entries.async_reload(entry.entry_id)

