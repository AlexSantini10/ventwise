"""Base entity helpers for the integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN, MANUFACTURER, NAME
from ..translation import runtime_catalog
from ..application.coordinator import VentWiseCoordinator
from ..application.runtime import RoomConfig


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
        self._attr_name = _localized_name(name_key, coordinator.hass.config.language)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.config_entry.title or NAME,
        )

    @property
    def suggested_object_id(self) -> str:
        """Keep the entity ID independent from the Home Assistant UI language."""

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
        super().__init__(
            coordinator,
            f"{room_key}_{entity_suffix}",
            name_key,
        )
        # Home Assistant prefixes entities with the room device object ID.
        # Keep only the English entity type here to avoid a doubled room key.
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


def _localized_name(name_key: str, language: str | None) -> str:
    """Return a translated entity label for the current backend language."""

    labels = runtime_catalog(language)["entity_name"]
    return labels.get(name_key, name_key.replace("_", " ").title())
    english_labels = ENTITY_NAME_LABELS["en"]
    return labels.get(
        name_key,
        english_labels.get(name_key, name_key.replace("_", " ").title()),
    )
