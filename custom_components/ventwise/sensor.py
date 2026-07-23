"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity, VentWiseRoomEntity
from .runtime import RoomConfig, build_debug_attributes, find_room_recommendation
from .ventwise_core import RecommendationAction


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensor entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    entities: list[SensorEntity] = [
        RecommendationStateSensor(coordinator),
        RecommendationScoreSensor(coordinator),
        RecommendationReasonSensor(coordinator),
        OutdoorTemperatureSensor(coordinator),
        OutdoorHumiditySensor(coordinator),
        WindSpeedSensor(coordinator),
    ]
    for room in coordinator.config.rooms:
        entities.extend(
            [
                RoomRecommendationStateSensor(coordinator, room),
                RoomRecommendationScoreSensor(coordinator, room),
                RoomRecommendationReasonSensor(coordinator, room),
                RoomOutdoorTemperatureSensor(coordinator, room),
                RoomOutdoorHumiditySensor(coordinator, room),
                RoomWindSpeedSensor(coordinator, room),
            ]
        )
    async_add_entities(entities)


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


class OutdoorTemperatureSensor(VentWiseEntity, SensorEntity):
    """Parsed outdoor temperature from the configured source."""

    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_temperature", "Outdoor temperature")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_temperature_c


class OutdoorHumiditySensor(VentWiseEntity, SensorEntity):
    """Parsed outdoor humidity from the configured source."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_humidity", "Outdoor humidity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_humidity_percent


class WindSpeedSensor(VentWiseEntity, SensorEntity):
    """Parsed outdoor wind speed from the configured source."""

    _attr_icon = "mdi:weather-windy"
    _attr_native_unit_of_measurement = "m/s"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "wind_speed", "Wind speed")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.wind_speed_m_s


class RoomRecommendationStateSensor(VentWiseRoomEntity, SensorEntity):
    """Current recommendation for a single room."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "recommendation", f"{room.name} recommendation")

    @property
    def native_value(self) -> str:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        if recommendation is None:
            return RecommendationAction.NONE.value
        return recommendation.action.value


class RoomRecommendationScoreSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation score for a single room."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "score", f"{room.name} score")

    @property
    def native_value(self) -> float:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return 0.0 if recommendation is None else recommendation.score


class RoomRecommendationReasonSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation reason for a single room."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "reason", f"{room.name} reason")

    @property
    def native_value(self) -> str:
        if not self.room.enabled:
            return "Room disabled."
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        if recommendation is None:
            return self.coordinator.data.summary.reason
        return recommendation.reason


class RoomOutdoorTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor temperature shown on a room device."""

    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_temperature", f"{room.name} outdoor temperature")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_temperature_c


class RoomOutdoorHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor humidity shown on a room device."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_humidity", f"{room.name} outdoor humidity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_humidity_percent


class RoomWindSpeedSensor(VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor wind speed shown on a room device."""

    _attr_icon = "mdi:weather-windy"
    _attr_native_unit_of_measurement = "m/s"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "wind_speed", f"{room.name} wind speed")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.wind_speed_m_s
