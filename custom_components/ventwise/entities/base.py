"""Base entity helpers for the integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..application.coordinator import VentWiseCoordinator
from ..application.runtime.integration_runtime import RoomConfig
from ..const import DOMAIN, MANUFACTURER, NAME


class VentWiseEntity(CoordinatorEntity[VentWiseCoordinator]):
    """Base entity for VentWise."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        entity_suffix: str,
        name_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_suffix}"
        self._suggested_object_id = entity_suffix
        self._attr_translation_key = name_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.config_entry.title or NAME,
        )

    @property
    def suggested_object_id(self) -> str:
        """Keep entity IDs independent from the Home Assistant UI language."""

        return self._suggested_object_id


class VentWiseRoomEntity(VentWiseEntity):
    """Base entity attached to a specific room device."""

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        room: RoomConfig,
        entity_suffix: str,
        name_key: str,
    ) -> None:
        room_key = room.room_id or room.name
        super().__init__(coordinator, f"{room_key}_{entity_suffix}", name_key)
        # Home Assistant prefixes entities with the room device object ID.
        # Keep only the technical entity type here to avoid a doubled room key.
        self._suggested_object_id = entity_suffix
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
