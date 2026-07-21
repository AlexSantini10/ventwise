"""Switch platform for VentWise."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up switch entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    async_add_entities([MasterEnableSwitch(coordinator)])


class MasterEnableSwitch(VentWiseEntity, SwitchEntity):
    """Master enable switch for the integration."""

    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "master_enable", "Master enable")

    @property
    def is_on(self) -> bool:
        return self.coordinator.config.enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(False)

