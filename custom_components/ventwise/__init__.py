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
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
            Platform.SWITCH,
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
            Platform.SWITCH,
        ],
    )
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when config entry options change."""

    await hass.config_entries.async_reload(entry.entry_id)
