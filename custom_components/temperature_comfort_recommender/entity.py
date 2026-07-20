"""Base entity helpers for the integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import TemperatureComfortRecommenderCoordinator


class TemperatureComfortEntity(CoordinatorEntity[TemperatureComfortRecommenderCoordinator]):
    """Base entity for the temperature comfort recommender."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TemperatureComfortRecommenderCoordinator,
        entity_suffix: str,
        friendly_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_suffix}"
        self._attr_name = friendly_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.config_entry.title or NAME,
        )
