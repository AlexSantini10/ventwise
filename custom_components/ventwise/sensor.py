"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity
from .runtime import build_debug_attributes


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


class RecommendationStateSensor(VentWiseEntity, SensorEntity):
    """Current recommendation as a sensor."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation", "Recommendation")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary.action.value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return build_debug_attributes(self.coordinator.config, self.coordinator.data)


class RecommendationScoreSensor(VentWiseEntity, SensorEntity):
    """Numeric recommendation score."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "score", "Score")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.summary.score

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return build_debug_attributes(self.coordinator.config, self.coordinator.data)


class RecommendationReasonSensor(VentWiseEntity, SensorEntity):
    """Human-readable recommendation reason."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "reason", "Reason")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary.reason

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return build_debug_attributes(self.coordinator.config, self.coordinator.data)
