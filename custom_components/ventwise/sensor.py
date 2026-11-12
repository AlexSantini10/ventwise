"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .application.coordinator import VentWiseCoordinator
from .application.notification import build_recommendation_explanation, build_recommendation_status
from .application.runtime import (
    RoomConfig,
    WINDOW_STATE_NOT_CONFIGURED,
    find_room_recommendation,
    state_to_float,
    state_to_temperature_c,
)
from .entities.base import VentWiseEntity, VentWiseRoomEntity
from .ventwise_core import RecommendationAction
from .units import display_value, temperature_from_celsius, wind_speed_from_m_s
from .const import DEFAULT_TEMPERATURE_UNIT, DEFAULT_WIND_SPEED_UNIT


class TemperatureUnitMixin:
    @property
    def native_unit_of_measurement(self):
        return getattr(self.coordinator.config, "temperature_unit", DEFAULT_TEMPERATURE_UNIT)

    def _temperature(self, value):
        return display_value(temperature_from_celsius(value, self.native_unit_of_measurement))


class WindSpeedUnitMixin:
    @property
    def native_unit_of_measurement(self):
        return getattr(self.coordinator.config, "wind_speed_unit", DEFAULT_WIND_SPEED_UNIT)

    def _wind_speed(self, value):
        return display_value(wind_speed_from_m_s(value, self.native_unit_of_measurement))


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
                RoomWindowStateSensor(coordinator, room),
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
        super().__init__(coordinator, "weather_condition", "weather_condition")

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


class PerceivedIndoorTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Average perceived indoor temperature across configured rooms."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_indoor_temperature",
            "average_perceived_indoor_temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.active_indoor_perceived_c)


class PerceivedOutdoorTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Current perceived outdoor temperature."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_outdoor_temperature",
            "perceived_outdoor_temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.outdoor_perceived_c)


class PerceivedComfortTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Current effective comfort temperature target."""

    _attr_icon = "mdi:thermometer-check"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "perceived_comfort_temperature",
            "effective_comfort_temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.target_perceived_c)


class SuggestedComfortTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Current suggested comfort temperature from the algorithm."""

    _attr_icon = "mdi:thermometer-auto"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(
            coordinator,
            "suggested_comfort_temperature",
            "suggested_comfort_temperature",
        )

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.suggested_comfort_temperature_c)


class OutdoorTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Parsed outdoor temperature from the configured source."""

    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_temperature", "outdoor_temperature")

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.outdoor_temperature_c)


class OutdoorHumiditySensor(VentWiseEntity, SensorEntity):
    """Parsed outdoor humidity from the configured source."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_humidity", "outdoor_humidity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_humidity_percent


class WindSpeedSensor(WindSpeedUnitMixin, VentWiseEntity, SensorEntity):
    """Parsed outdoor wind speed from the configured source."""

    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "wind_speed", "wind_speed")

    @property
    def native_value(self) -> float | None:
        return self._wind_speed(self.coordinator.data.wind_speed_m_s)


class RoomRecommendationStateSensor(VentWiseRoomEntity, SensorEntity):
    """Current recommendation for a single room."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "recommendation", "recommendation")

    @property
    def native_value(self) -> str:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        if recommendation is None:
            return RecommendationAction.NONE.value
        return recommendation.action.value

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the stable deterministic explanation on the action entity."""

        decision = getattr(self.coordinator.data, "decision", None)
        if decision is None:
            return {}
        room_id = self.room.room_id or self.room.name
        result = next((item for item in decision.room_results if item.room_id == room_id), None)
        if result is None:
            return {}
        return {
            "core_action": result.core_action.value,
            "delivered_action": result.delivered_action.value,
            "reason_code": result.reason_code,
            "duration_minutes": result.duration_minutes,
            "confidence": result.confidence,
            "candidates": {
                "open": result.candidate_scores.open,
                "ventilate": result.candidate_scores.ventilate,
                "close": result.candidate_scores.close,
            },
            "trace": [{"code": entry.code, "detail": entry.detail} for entry in result.trace],
            "blocked_conditions": list(result.blocked_conditions),
            "applied_penalties": list(result.applied_penalties),
            "data_quality": {
                "used": list(result.data_quality.used),
                "discarded": list(result.data_quality.discarded),
                "awaiting_source": list(result.data_quality.awaiting_source),
            },
            "delivery_suppressed_by": result.delivery_suppressed_by,
        }


class RoomRecommendationScoreSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation score for a single room."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "score", "recommendation_score")

    @property
    def native_value(self) -> float:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return 0.0 if recommendation is None else recommendation.score


class RoomRecommendationReasonSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation reason for a single room."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "reason", "recommendation_reason")

    @property
    def native_value(self) -> str:
        if not self.room.enabled:
            return build_recommendation_status(
                blocked_by="disabled",
                language=self.hass.config.language,
            )
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        if recommendation is None:
            return build_recommendation_status(
                blocked_by=self.coordinator.data.summary.blocked_by,
                language=self.hass.config.language,
            )
        return build_recommendation_explanation(
            recommendation,
            language=self.hass.config.language,
        )


class RoomWindowStateSensor(VentWiseRoomEntity, SensorEntity):
    """Aggregated open/closed state from the room's optional contacts."""

    _attr_icon = "mdi:window-shutter-cog"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "window_state", "window_state")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.window_states.get(
            self.room.room_id or self.room.name,
            WINDOW_STATE_NOT_CONFIGURED,
        )


class RoomWeatherConditionSensor(VentWiseRoomEntity, SensorEntity):
    """Current weather condition shown on a room device."""

    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "weather_condition", "weather_condition")

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


class RoomPerceivedIndoorTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Perceived indoor temperature for a room."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_indoor_temperature",
            "perceived_indoor_temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else self._temperature(recommendation.indoor_perceived_c)


class RoomPerceivedOutdoorTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Perceived outdoor temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_outdoor_temperature",
            "perceived_outdoor_temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else self._temperature(recommendation.outdoor_perceived_c)


class RoomPerceivedComfortTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Effective comfort temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-check"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "perceived_comfort_temperature",
            "effective_comfort_temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else self._temperature(recommendation.target_perceived_c)


class RoomSuggestedComfortTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Suggested comfort temperature shown on a room device."""

    _attr_icon = "mdi:thermometer-auto"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(
            coordinator,
            room,
            "suggested_comfort_temperature",
            "suggested_comfort_temperature",
        )

    @property
    def native_value(self) -> float | None:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return None if recommendation is None else self._temperature(recommendation.suggested_comfort_temperature_c)


class RoomIndoorTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Current indoor temperature for a single room."""

    _attr_icon = "mdi:home-thermometer"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_temperature", "temperature")

    @property
    def native_value(self) -> float | None:
        return self._temperature(state_to_temperature_c(self.hass.states.get(self.room.temperature_entity_id)))


class RoomIndoorHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Current indoor humidity for a single room."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_humidity", "indoor_humidity")

    @property
    def native_value(self) -> float | None:
        if not self.room.humidity_entity_id:
            return None
        return state_to_float(self.hass.states.get(self.room.humidity_entity_id))


class RoomOutdoorTemperatureSensor(TemperatureUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor temperature shown on a room device."""

    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_temperature", "outdoor_temperature")

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.outdoor_temperature_c)


class RoomOutdoorHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor humidity shown on a room device."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_humidity", "outdoor_humidity")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_humidity_percent


class RoomWindSpeedSensor(WindSpeedUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor wind speed shown on a room device."""

    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "wind_speed", "wind_speed")

    @property
    def native_value(self) -> float | None:
        return self._wind_speed(self.coordinator.data.wind_speed_m_s)
