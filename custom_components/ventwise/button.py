"""Button entities for VentWise."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up VentWise buttons."""

    coordinator: VentWiseCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities([VentWiseRequestRecommendationButton(coordinator)])


class VentWiseRequestRecommendationButton(VentWiseEntity, ButtonEntity):
    """Request an informational recommendation immediately."""

    _attr_icon = "mdi:message-text-fast-outline"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        """Initialize the button."""

        super().__init__(coordinator, "request_recommendation", "request_recommendation")

    async def async_press(self) -> None:
        """Refresh data and send the current recommendations immediately."""

        await self.coordinator.async_send_on_demand_recommendation()
