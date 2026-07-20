"""Sensor platform for Temperature Comfort Recommender."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .coordinator import TemperatureComfortRecommenderCoordinator
from .entity import TemperatureComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensor entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    async_add_entities(
        [
            RecommendationStateSensor(coordinator),
            RecommendationScoreSensor(coordinator),
            RecommendationReasonSensor(coordinator),
        ]
    )


class RecommendationStateSensor(TemperatureComfortEntity, SensorEntity):
    """Current recommendation as a sensor."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: TemperatureComfortRecommenderCoordinator) -> None:
        super().__init__(coordinator, "recommendation", "Recommendation")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary.action.value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        snapshot = self.coordinator.data
        summary = snapshot.summary
        return {
            "score": summary.score,
            "reason": summary.reason,
            "best_room": summary.best_room,
            "blocked_by": summary.blocked_by,
            "notification_allowed": snapshot.notification_allowed,
            "quiet_hours_active": snapshot.quiet_hours_active,
            "cooldown_active": snapshot.cooldown_active,
            "stable_for_seconds": snapshot.stable_for_seconds,
        }


class RecommendationScoreSensor(TemperatureComfortEntity, SensorEntity):
    """Numeric recommendation score."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: TemperatureComfortRecommenderCoordinator) -> None:
        super().__init__(coordinator, "score", "Score")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.summary.score


class RecommendationReasonSensor(TemperatureComfortEntity, SensorEntity):
    """Human-readable recommendation reason."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: TemperatureComfortRecommenderCoordinator) -> None:
        super().__init__(coordinator, "reason", "Reason")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary.reason

