"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .application.coordinator import VentWiseCoordinator
from .application.notification import build_recommendation_explanation, build_recommendation_status
from .application.runtime import (
    RoomConfig,
    WINDOW_STATE_NOT_CONFIGURED,
    build_debug_attributes,
    find_room_recommendation,
    build_room_diagnostic_attributes,
    room_co2_reading,
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
        AggregateRecommendationSensor(coordinator),
        AggregateRecommendationScoreSensor(coordinator),
        AggregateRecommendationReasonSensor(coordinator),
        AggregateCalculatedRecommendationSensor(coordinator),
        WeatherConditionSensor(coordinator),
        PerceivedIndoorTemperatureSensor(coordinator),
        PerceivedOutdoorTemperatureSensor(coordinator),
        PerceivedComfortTemperatureSensor(coordinator),
        SuggestedComfortTemperatureSensor(coordinator),
        OutdoorTemperatureSensor(coordinator),
        OutdoorHumiditySensor(coordinator),
        OutdoorPressureSensor(coordinator),
        WindSpeedSensor(coordinator),
        WindGustSensor(coordinator),
        ForecastTemperatureSensor(coordinator),
    ]
    for room in coordinator.config.rooms:
        entities.extend(
            [
                RoomRecommendationStateSensor(coordinator, room),
                RoomRecommendationScoreSensor(coordinator, room),
                RoomRecommendationConfidenceSensor(coordinator, room),
                RoomVentilationScoreSensor(coordinator, room),
                RoomRecommendationReasonSensor(coordinator, room),
                RoomCalculatedRecommendationSensor(coordinator, room),
                RoomWindowStateSensor(coordinator, room),
                RoomWeatherConditionSensor(coordinator, room),
                RoomPerceivedIndoorTemperatureSensor(coordinator, room),
                RoomPerceivedOutdoorTemperatureSensor(coordinator, room),
                RoomPerceivedComfortTemperatureSensor(coordinator, room),
                RoomSuggestedComfortTemperatureSensor(coordinator, room),
                RoomIndoorTemperatureSensor(coordinator, room),
                RoomIndoorHumiditySensor(coordinator, room),
                RoomCo2Sensor(coordinator, room),
                RoomOutdoorTemperatureSensor(coordinator, room),
                RoomOutdoorHumiditySensor(coordinator, room),
                RoomWindSpeedSensor(coordinator, room),
            ]
        )
    async_add_entities(entities)


def _room_core_result(coordinator: VentWiseCoordinator, room: RoomConfig):
    """Return the latest core result for a configured room."""

    room_id = room.room_id or room.name
    return next(
        (
            result
            for result in (coordinator.data.core_result.room_results if coordinator.data.core_result else ())
            if result.room_id == room_id
        ),
        None,
    )


class AggregateRecommendationSensor(VentWiseEntity, SensorEntity):
    """Aggregate core recommendation across enabled rooms."""

    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation", "recommendation")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary.action.value

    @property
    def extra_state_attributes(self) -> dict:
        return build_debug_attributes(self.coordinator.config, self.coordinator.data)


class AggregateRecommendationScoreSensor(VentWiseEntity, SensorEntity):
    """Aggregate recommendation score across enabled rooms."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation_score", "recommendation_score")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.summary.score


class AggregateRecommendationReasonSensor(VentWiseEntity, SensorEntity):
    """Localized aggregate recommendation explanation."""

    _attr_icon = "mdi:text-box-outline"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "recommendation_reason", "recommendation_reason")

    @property
    def native_value(self) -> str:
        summary = self.coordinator.data.summary
        if summary.best_room:
            recommendation = next(
                (item for item in summary.room_recommendations if item.room_name == summary.best_room),
                None,
            )
            if recommendation is not None:
                return build_recommendation_explanation(
                    recommendation,
                    language=self.hass.config.language,
                )
        return build_recommendation_status(
            blocked_by=summary.blocked_by,
            language=self.hass.config.language,
        )


class AggregateCalculatedRecommendationSensor(VentWiseEntity, SensorEntity):
    """Immediate aggregate recommendation before stabilization guardrails."""

    _attr_icon = "mdi:calculator-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "core_recommendation", "core_recommendation")

    @property
    def native_value(self) -> str:
        result = self.coordinator.data.calculated_result
        return RecommendationAction.NONE.value if result is None else result.core_action.value


class ForecastTemperatureSensor(TemperatureUnitMixin, VentWiseEntity, SensorEntity):
    """Nearest forecast temperature used by the runtime."""

    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "forecast_temperature", "forecast_temperature")

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.coordinator.data.forecast_temperature_c)


class OutdoorPressureSensor(VentWiseEntity, SensorEntity):
    """Current outdoor atmospheric pressure."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "hPa"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_pressure", "outdoor_pressure")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.outdoor_pressure_hpa


class WindGustSensor(WindSpeedUnitMixin, VentWiseEntity, SensorEntity):
    """Current outdoor wind gust."""

    _attr_icon = "mdi:weather-windy-variant"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "wind_gust", "wind_gust")

    @property
    def native_value(self) -> float | None:
        return self._wind_speed(self.coordinator.data.wind_gust_m_s)


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
    def extra_state_attributes(self) -> dict:
        """Expose structured core output without localized presentation text."""

        snapshot = self.coordinator.data
        if snapshot is None:
            return {}
        return build_room_diagnostic_attributes(
            snapshot,
            self.room.room_id or self.room.name,
        )


class RoomRecommendationScoreSensor(VentWiseRoomEntity, SensorEntity):
    """Recommendation score for a single room."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "score", "recommendation_score")

    @property
    def native_value(self) -> float:
        recommendation = find_room_recommendation(self.coordinator.data.summary, self.room)
        return 0.0 if recommendation is None else recommendation.score


class RoomRecommendationConfidenceSensor(VentWiseRoomEntity, SensorEntity):
    """Core confidence for the room recommendation."""

    _attr_icon = "mdi:percent-outline"
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "confidence", "recommendation_confidence")

    @property
    def native_value(self) -> float | None:
        result = _room_core_result(self.coordinator, self.room)
        return None if result is None else round(result.confidence * 100.0, 2)


class RoomVentilationScoreSensor(VentWiseRoomEntity, SensorEntity):
    """Core short-ventilation candidate score for the room."""

    _attr_icon = "mdi:fan-clock"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "ventilation_score", "ventilation_score")

    @property
    def native_value(self) -> float | None:
        result = _room_core_result(self.coordinator, self.room)
        return None if result is None else result.candidate_scores.ventilate


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


class RoomCalculatedRecommendationSensor(VentWiseRoomEntity, SensorEntity):
    """Immediate room recommendation before stabilization guardrails."""

    _attr_icon = "mdi:calculator-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "core_recommendation", "core_recommendation")

    @property
    def native_value(self) -> str:
        room_id = self.room.room_id or self.room.name
        result = next(
            (
                item
                for item in (
                    self.coordinator.data.calculated_result.room_results
                    if self.coordinator.data.calculated_result
                    else ()
                )
                if item.room_id == room_id
            ),
            None,
        )
        return RecommendationAction.NONE.value if result is None else result.core_action.value


class RoomCo2Sensor(VentWiseRoomEntity, SensorEntity):
    """Effective indoor CO₂ reading used by the decision engine."""

    _attr_icon = "mdi:molecule-co2"
    _attr_native_unit_of_measurement = "ppm"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "co2", "co2")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Expose ppm only while the state contains a numeric reading."""

        value, _ = room_co2_reading(self.room, self.hass.states.get)
        return "ppm" if value is not None else None

    @property
    def native_value(self) -> float | str:
        if not self.room.co2_enabled:
            return "disabled"
        if not self.room.co2_entity_id:
            return "not_configured"
        value, _ = room_co2_reading(
            self.room,
            self.hass.states.get,
        )
        if value is None:
            return "sensor_unavailable"
        if value is not None and value.is_integer():
            return int(value)
        return value


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
