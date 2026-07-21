"""Binary sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ventwise_core import RecommendationAction

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up binary sensor entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    async_add_entities(
        [
            RecommendationActiveBinarySensor(coordinator),
            QuietHoursBinarySensor(coordinator),
            CooldownBinarySensor(coordinator),
        ]
    )


class RecommendationActiveBinarySensor(VentWiseEntity, BinarySensorEntity):
    """Whether a recommendation is currently actionable."""

    _attr_icon = "mdi:window-open"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation_active", "Recommendation active")

    @property
    def is_on(self) -> bool:
        snapshot = self.coordinator.data
        return snapshot.summary.action != RecommendationAction.NONE and snapshot.notification_allowed


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
