"""Button entities for VentWise."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .application.coordinator import VentWiseCoordinator
from .application.runtime import RoomConfig
from .entities.base import VentWiseEntity, VentWiseRoomEntity
from .ventwise_core import RecommendationAction

_DEBUG_BUTTON_SUFFIXES = ("_debug_open_notification", "_debug_close_notification")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up VentWise buttons."""

    coordinator: VentWiseCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    entities: list[ButtonEntity] = [VentWiseRequestRecommendationButton(coordinator)]
    if coordinator.config.debug_mode_enabled:
        for room in coordinator.config.rooms:
            entities.extend(
                [
                    VentWiseDebugOpenNotificationButton(coordinator, room),
                    VentWiseDebugCloseNotificationButton(coordinator, room),
                ]
            )
    else:
        _remove_debug_button_registry_entries(hass, entry.entry_id)
    async_add_entities(entities)


def _remove_debug_button_registry_entries(hass: HomeAssistant, entry_id: str) -> None:
    """Remove stale debug controls when debug mode is disabled."""

    registry = er.async_get(hass)
    for registry_entry in tuple(registry.entities.values()):
        unique_id = registry_entry.unique_id or ""
        if (
            registry_entry.config_entry_id == entry_id
            and unique_id.startswith(f"{entry_id}_")
            and unique_id.endswith(_DEBUG_BUTTON_SUFFIXES)
        ):
            registry.async_remove(registry_entry.entity_id)


class VentWiseRequestRecommendationButton(VentWiseEntity, ButtonEntity):
    """Request an informational recommendation immediately."""

    _attr_icon = "mdi:message-text-fast-outline"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        """Initialize the button."""

        super().__init__(coordinator, "request_recommendation", "request_recommendation")

    async def async_press(self) -> None:
        """Refresh data and send the current recommendations immediately."""

        await self.coordinator.async_send_on_demand_recommendation()


class _VentWiseDebugNotificationButton(VentWiseRoomEntity, ButtonEntity):
    """Send a forced operational notification for one room in debug mode."""

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        room: RoomConfig,
        action: RecommendationAction,
        entity_suffix: str,
        name_key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, room, entity_suffix, name_key)
        self._action = action
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Send the forced debug notification."""

        await self.coordinator.async_send_debug_room_notification(self.room, self._action)


class VentWiseDebugOpenNotificationButton(_VentWiseDebugNotificationButton):
    """Send a debug open-window notification for one room."""

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            RecommendationAction.OPEN,
            "debug_open_notification",
            "debug_open_notification",
            "mdi:window-open-variant",
        )


class VentWiseDebugCloseNotificationButton(_VentWiseDebugNotificationButton):
    """Send a debug close-window notification for one room."""

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            RecommendationAction.CLOSE,
            "debug_close_notification",
            "debug_close_notification",
            "mdi:window-closed-variant",
        )
