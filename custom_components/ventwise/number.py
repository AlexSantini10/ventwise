"""Number platform for VentWise."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up number entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    async_add_entities([StabilityMinutesNumber(coordinator)])


class StabilityMinutesNumber(VentWiseEntity, NumberEntity):
    """Global minimum stability requirement in minutes."""

    _attr_icon = "mdi:timer-sand"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 24 * 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "stability_minutes", "Stability minutes")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config.stability_minutes)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_stability_minutes(int(value))
