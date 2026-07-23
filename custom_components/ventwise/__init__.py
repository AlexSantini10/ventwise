"""VentWise integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import DOMAIN, NAME

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import VentWiseCoordinator
    VentWiseCoordinator = Any  # type: ignore[assignment]
else:
    ConfigEntry = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]
    VentWiseCoordinator = Any  # type: ignore[assignment]


@dataclass(slots=True)
class IntegrationRuntimeData:
    """Runtime storage for the integration."""

    coordinator: VentWiseCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    from homeassistant.const import Platform

    from .coordinator import VentWiseCoordinator

    coordinator = VentWiseCoordinator(
        hass,
        entry,
        {**entry.data, **entry.options},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IntegrationRuntimeData(
        coordinator=coordinator
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    from homeassistant.const import Platform

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
    return unload_ok
