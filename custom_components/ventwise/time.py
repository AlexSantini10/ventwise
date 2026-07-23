"""Time platform for VentWise."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up time entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    async_add_entities(
        [
            QuietHoursStartTime(coordinator),
            QuietHoursEndTime(coordinator),
        ]
    )


class QuietHoursStartTime(VentWiseEntity, TimeEntity):
    """Start time for quiet hours."""

    _attr_icon = "mdi:clock-start"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "quiet_hours_start", "Quiet hours start time")

    @property
    def native_value(self) -> time | None:
        return _parse_time(self.coordinator.config.quiet_hours_start)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_quiet_hours_start(value.isoformat())


class QuietHoursEndTime(VentWiseEntity, TimeEntity):
    """End time for quiet hours."""

    _attr_icon = "mdi:clock-end"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "quiet_hours_end", "Quiet hours end time")

    @property
    def native_value(self) -> time | None:
        return _parse_time(self.coordinator.config.quiet_hours_end)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_quiet_hours_end(value.isoformat())


def _parse_time(value: str) -> time | None:
    parts = str(value).strip().split(":")
    if len(parts) == 2:
        parts.append("00")
    if len(parts) != 3:
        return None
    try:
        return time(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
