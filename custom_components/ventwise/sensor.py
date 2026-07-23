"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity, VentWiseRoomEntity
from .runtime import (
    RoomConfig,
    find_room_recommendation,
    room_target_temperature_c,
    state_to_float,
)
from .ventwise_core import RecommendationAction


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensor entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    entities: list[SensorEntity] = [
        WeatherConditionSensor(coordinator),
        PerceivedIndoorTemperatureSensor(coordinator),
        PerceivedOutdoorTemperatureSensor(coordinator),
        PerceivedComfortTemperatureSensor(coordinator),
        SuggestedComfortTemperatureSensor(coordinator),
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
                RoomWeatherConditionSensor(coordinator, room),
                RoomPerceivedIndoorTemperatureSensor(coordinator, room),
                RoomPerceivedOutdoorTemperatureSensor(coordinator, room),
                RoomPerceivedComfortTemperatureSensor(coordinator, room),
                RoomSuggestedComfortTemperatureSensor(coordinator, room),
                RoomIndoorTemperatureSensor(coordinator, room),
                RoomIndoorHumiditySensor(coordinator, room),
                RoomOutdoorTemperatureSensor(coordinator, room),
                RoomOutdoorHumiditySensor(coordinator, room),
                RoomWindSpeedSensor(coordinator, room),
            ]
    )
    async_add_entities(entities)


class WeatherConditionSensor(VentWiseEntity, SensorEntity):
    """Current weather condition from the configured weather entity."""

    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "weather_condition", "Current weather condition")

    @property
    def native_value(self) -> str | None:
        weather_entity_id = self.coordinator.config.outdoor_weather_entity_id
        if not weather_entity_id:
            return None
        state = self.hass.states.get(weather_entity_id)
        if state is None:
            return None
        raw_state = getattr(state, "state", None)
        if raw_state is None:
            return None
        text = str(raw_state).strip()
        return text or None


class PerceivedIndoorTemperatureSensor(VentWiseEntity, SensorEntity):
    """Average perceived indoor temperature across configured rooms."""

    _attr_icon = "mdi:thermometer-lines"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_indoor_temperature",
            "Average perceived indoor temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.active_indoor_perceived_c


class PerceivedOutdoorTemperatureSensor(VentWiseEntity, SensorEntity):
    """Current perceived outdoor temperature."""

    _attr_icon = "mdi:thermometer-lines"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_outdoor_temperature",
            "Current perceived outdoor temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_perceived_c


class PerceivedComfortTemperatureSensor(VentWiseEntity, SensorEntity):
    """Current effective comfort temperature target."""

    _attr_icon = "mdi:thermometer-check"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_comfort_temperature",
            "Effective comfort temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.target_perceived_c


class SuggestedComfortTemperatureSensor(VentWiseEntity, SensorEntity):
    """Current suggested comfort temperature from the algorithm."""

    _attr_icon = "mdi:thermometer-auto"
    _attr_native_unit_of_measurement = "Â°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "suggested_comfort_temperature",
            "Suggested comfort temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.suggested_comfort_temperature_c


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
        super().__init__(coordinator, "wind_speed", "Outdoor wind speed")

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
        super().__init__(coordinator, room, "score", f"{room.name} recommendation score")

    @property
    def native_value(self) -> float:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return 0.0 if recommendation is None else recommendation.score


class RoomRecommendationReasonSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation reason for a single room."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "reason", f"{room.name} recommendation reason")

    @property
    def native_value(self) -> str:
        if not self.room.enabled:
            return "Room disabled."
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        if recommendation is None:
            return self.coordinator.data.summary.reason
        return recommendation.reason


class RoomWeatherConditionSensor(VentWiseRoomEntity, SensorEntity):
    """Current weather condition shown on a room device."""

    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "weather_condition", f"{room.name} weather condition")

    @property
    def native_value(self) -> str | None:
        weather_entity_id = self.coordinator.config.outdoor_weather_entity_id
        if not weather_entity_id:
            return None
        state = self.hass.states.get(weather_entity_id)
        if state is None:
            return None
        raw_state = getattr(state, "state", None)
        if raw_state is None:
            return None
        text = str(raw_state).strip()
        return text or None


class RoomPerceivedIndoorTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Perceived indoor temperature for a room."""

    _attr_icon = "mdi:thermometer-lines"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_indoor_temperature",
            f"{room.name} perceived indoor temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else recommendation.indoor_perceived_c


class RoomPerceivedOutdoorTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Perceived outdoor temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-lines"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_outdoor_temperature",
            f"{room.name} perceived outdoor temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else recommendation.outdoor_perceived_c


class RoomPerceivedComfortTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Effective comfort temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-check"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_comfort_temperature",
            f"{room.name} effective comfort temperature",
        )

    @property
    def native_value(self) -> float | None:
        return room_target_temperature_c(self.room, self.coordinator.config)


class RoomSuggestedComfortTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Suggested comfort temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-auto"
    _attr_native_unit_of_measurement = "Â°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "suggested_comfort_temperature",
            f"{room.name} suggested comfort temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else recommendation.suggested_comfort_temperature_c


class RoomIndoorTemperatureSensor(VentWiseRoomEntity, SensorEntity):
    """Current indoor temperature for a single room."""

    _attr_icon = "mdi:home-thermometer"
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_temperature", f"{room.name} temperature")

    @property
    def native_value(self) -> float | None:
        return state_to_float(self.hass.states.get(self.room.temperature_entity_id))


class RoomIndoorHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Current indoor humidity for a single room."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_humidity", f"{room.name} indoor humidity")

    @property
    def native_value(self) -> float | None:
        if not self.room.humidity_entity_id:
            return None
        return state_to_float(self.hass.states.get(self.room.humidity_entity_id))


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
        super().__init__(coordinator, room, "wind_speed", f"{room.name} outdoor wind speed")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.wind_speed_m_s
