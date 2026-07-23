"""Base entity helpers for the integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import VentWiseCoordinator
from .runtime import RoomConfig


class VentWiseEntity(CoordinatorEntity[VentWiseCoordinator]):
    """Base entity for VentWise."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
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


class VentWiseRoomEntity(VentWiseEntity):
    """Base entity attached to a specific room device."""

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        room: RoomConfig,
        entity_suffix: str,
        friendly_name: str,
    ) -> None:
        room_key = room.room_id or room.name
        super().__init__(
            coordinator,
            f"{room_key}_{entity_suffix}",
            friendly_name,
        )
        self._room = room
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id, room_key)},
            manufacturer=MANUFACTURER,
            name=room.name,
        )

    @property
    def room(self) -> RoomConfig:
        """Return the associated room config."""

        return self._room
