"""Binary sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ventwise_core import RecommendationAction

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity, VentWiseRoomEntity
from .runtime import find_room_recommendation


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up binary sensor entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    entities: list[BinarySensorEntity] = [
        RecommendationActiveBinarySensor(coordinator),
        NotificationAllowedBinarySensor(coordinator),
        QuietHoursBinarySensor(coordinator),
        CooldownBinarySensor(coordinator),
    ]
    for room in coordinator.config.rooms:
        entities.append(RoomRecommendationActiveBinarySensor(coordinator, room))
    async_add_entities(entities)


class RecommendationActiveBinarySensor(VentWiseEntity, BinarySensorEntity):
    """Whether a recommendation is currently actionable."""

    _attr_icon = "mdi:window-open"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation_active", "Recommendation active")

    @property
    def is_on(self) -> bool:
        snapshot = self.coordinator.data
        return snapshot.enabled and snapshot.summary.action != RecommendationAction.NONE


class NotificationAllowedBinarySensor(VentWiseEntity, BinarySensorEntity):
    """Whether VentWise is allowed to send a notification now."""

    _attr_icon = "mdi:bell-check"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "notification_allowed", "Notification allowed")

    @property
    def is_on(self) -> bool:
        snapshot = self.coordinator.data
        return snapshot.enabled and snapshot.notification_allowed


class QuietHoursBinarySensor(VentWiseEntity, BinarySensorEntity):
    """Whether quiet hours are currently active."""

    _attr_icon = "mdi:minus-circle-outline"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "quiet_hours", "Quiet hours")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.quiet_hours_active


class CooldownBinarySensor(VentWiseEntity, BinarySensorEntity):
    """Whether the notification cooldown is currently active."""

    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "cooldown", "Cooldown")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.cooldown_active


class RoomRecommendationActiveBinarySensor(VentWiseRoomEntity, BinarySensorEntity):
    """Whether a room currently has an actionable recommendation."""

    _attr_icon = "mdi:home-lightbulb-outline"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "active", f"{room.name} active")

    @property
    def is_on(self) -> bool:
        if not self.room.enabled:
            return False
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return recommendation is not None and recommendation.action != RecommendationAction.NONE
