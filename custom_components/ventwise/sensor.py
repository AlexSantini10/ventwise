"""Sensor platform for VentWise."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .application.coordinator import VentWiseCoordinator
from .application.notifications.service import build_recommendation_explanation, build_recommendation_status
from .application.runtime.integration_runtime import (
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
try:
    from .ventwise_core import (
        RecommendationAction,
        absolute_humidity_g_m3,
        humidity_ratio_g_kg,
        moisture_exchange_direction,
        pressure_hpa_or_default,
        vapor_pressure_hpa,
    )
except ImportError:  # Local source-tree development uses the standalone package.
    from ventwise_core import (
        RecommendationAction,
        absolute_humidity_g_m3,
        humidity_ratio_g_kg,
        moisture_exchange_direction,
        pressure_hpa_or_default,
        vapor_pressure_hpa,
    )
from .units import (
    display_value,
    normalize_measurement,
    state_unit,
    temperature_from_celsius,
    wind_speed_from_m_s,
)
from .const import DEFAULT_TEMPERATURE_UNIT, DEFAULT_WIND_SPEED_UNIT


class TemperatureUnitMixin:
    @property
    def native_unit_of_measurement(self):
        return getattr(self.coordinator.config, "temperature_unit", DEFAULT_TEMPERATURE_UNIT)

    def _temperature(self, value):
        converted = temperature_from_celsius(value, self.native_unit_of_measurement)
        return None if converted is None else round(display_value(converted), 2)


class WindSpeedUnitMixin:
    @property
    def native_unit_of_measurement(self):
        return getattr(self.coordinator.config, "wind_speed_unit", DEFAULT_WIND_SPEED_UNIT)

    def _wind_speed(self, value):
        converted = wind_speed_from_m_s(value, self.native_unit_of_measurement)
        return None if converted is None else round(display_value(converted), 2)


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
        OutdoorAbsoluteHumiditySensor(coordinator),
        OutdoorHumidityRatioSensor(coordinator),
        OutdoorVaporPressureSensor(coordinator),
        IndoorOutdoorHumidityDifferenceSensor(coordinator),
        MoistureExchangeDirectionSensor(coordinator),
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
                RoomIndoorAbsoluteHumiditySensor(coordinator, room),
                RoomIndoorHumidityRatioSensor(coordinator, room),
                RoomIndoorVaporPressureSensor(coordinator, room),
                RoomCo2Sensor(coordinator, room),
                RoomOutdoorTemperatureSensor(coordinator, room),
                RoomOutdoorHumiditySensor(coordinator, room),
                RoomOutdoorAbsoluteHumiditySensor(coordinator, room),
                RoomOutdoorHumidityRatioSensor(coordinator, room),
                RoomOutdoorVaporPressureSensor(coordinator, room),
                RoomIndoorOutdoorHumidityDifferenceSensor(coordinator, room),
                RoomMoistureExchangeDirectionSensor(coordinator, room),
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


def _outdoor_reading(coordinator: VentWiseCoordinator):
    """Return the normalized outdoor observation, when available."""

    core_snapshot = getattr(coordinator.data, "core_snapshot", None)
    return None if core_snapshot is None else core_snapshot.outdoor


def _room_reading(coordinator: VentWiseCoordinator, room: RoomConfig):
    """Return the normalized room observation, when available."""

    core_snapshot = getattr(coordinator.data, "core_snapshot", None)
    if core_snapshot is None:
        return None
    room_id = room.room_id or room.name
    return next((item for item in core_snapshot.rooms if item.room_id == room_id), None)


def _psychrometric_values(temperature_c, humidity_percent, pressure_hpa=None):
    """Return calculated moisture values for a normalized reading."""

    if temperature_c is None or humidity_percent is None:
        return None
    try:
        pressure, pressure_estimated = pressure_hpa_or_default(pressure_hpa)
        return {
            "absolute": round(absolute_humidity_g_m3(temperature_c, humidity_percent), 2),
            "ratio": round(humidity_ratio_g_kg(temperature_c, humidity_percent, pressure), 2),
            "vapor_pressure": round(vapor_pressure_hpa(temperature_c, humidity_percent), 2),
            "pressure_estimated": pressure_estimated,
        }
    except (TypeError, ValueError):
        return None


def _outdoor_psychrometrics(coordinator: VentWiseCoordinator):
    """Return outdoor calculated values from normalized coordinator data."""

    reading = _outdoor_reading(coordinator)
    if reading is not None:
        return _psychrometric_values(
            reading.temperature_c.value,
            reading.humidity_percent.value if reading.humidity_percent else None,
            reading.pressure_hpa.value if reading.pressure_hpa else None,
        )
    snapshot = coordinator.data
    return _psychrometric_values(
        snapshot.outdoor_temperature_c,
        snapshot.outdoor_humidity_percent,
        snapshot.outdoor_pressure_hpa,
    )


def _room_psychrometrics(coordinator: VentWiseCoordinator, room: RoomConfig):
    """Return room indoor calculated values from normalized data."""

    reading = _room_reading(coordinator, room)
    if reading is None or reading.humidity_percent is None:
        return None
    outdoor = _outdoor_reading(coordinator)
    pressure = outdoor.pressure_hpa.value if outdoor and outdoor.pressure_hpa else None
    return _psychrometric_values(
        reading.temperature_c.value,
        reading.humidity_percent.value,
        pressure,
    )


def _room_outdoor_psychrometrics(coordinator: VentWiseCoordinator, room: RoomConfig):
    """Return the shared outdoor calculated values for a room device."""

    return _outdoor_psychrometrics(coordinator)


def _room_humidity_delta(coordinator: VentWiseCoordinator, room: RoomConfig):
    """Return outdoor minus indoor absolute humidity for a room."""

    outdoor = _outdoor_psychrometrics(coordinator)
    indoor = _room_psychrometrics(coordinator, room)
    if outdoor is None or indoor is None:
        return None
    return round(outdoor["absolute"] - indoor["absolute"], 2)


def _global_humidity_delta(coordinator: VentWiseCoordinator):
    """Return outdoor minus average indoor absolute humidity."""

    outdoor = _outdoor_psychrometrics(coordinator)
    if outdoor is None:
        return None
    values = []
    for room in coordinator.config.rooms:
        indoor = _room_psychrometrics(coordinator, room)
        if indoor is not None:
            values.append(indoor["absolute"])
    if not values:
        return None
    return round(outdoor["absolute"] - sum(values) / len(values), 2)


def _global_moisture_direction(coordinator: VentWiseCoordinator):
    """Return the moisture exchange direction against average indoor air."""

    outdoor = _outdoor_psychrometrics(coordinator)
    if outdoor is None:
        return None
    values = []
    for room in coordinator.config.rooms:
        indoor = _room_psychrometrics(coordinator, room)
        if indoor is not None:
            values.append(indoor["absolute"])
    if not values:
        return None
    return moisture_exchange_direction(sum(values) / len(values), outdoor["absolute"])


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
        return round(self.coordinator.data.summary.score, 2)


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
        value = self.coordinator.data.outdoor_pressure_hpa
        return None if value is None else round(value, 2)


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
        value = self.coordinator.data.outdoor_humidity_percent
        return None if value is None else round(value, 2)


class OutdoorAbsoluteHumiditySensor(VentWiseEntity, SensorEntity):
    """Calculated outdoor absolute humidity."""

    _attr_icon = "mdi:water-opacity"
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_absolute_humidity", "outdoor_absolute_humidity")

    @property
    def native_value(self) -> float | None:
        values = _outdoor_psychrometrics(self.coordinator)
        return None if values is None else values["absolute"]


class OutdoorHumidityRatioSensor(VentWiseEntity, SensorEntity):
    """Calculated outdoor humidity ratio."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "g/kg"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_humidity_ratio", "outdoor_humidity_ratio")

    @property
    def native_value(self) -> float | None:
        values = _outdoor_psychrometrics(self.coordinator)
        return None if values is None else values["ratio"]

    @property
    def extra_state_attributes(self) -> dict:
        values = _outdoor_psychrometrics(self.coordinator)
        return {} if values is None else {"pressure_estimated": values["pressure_estimated"]}


class OutdoorVaporPressureSensor(VentWiseEntity, SensorEntity):
    """Calculated outdoor water vapor pressure."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "hPa"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "outdoor_vapor_pressure", "outdoor_vapor_pressure")

    @property
    def native_value(self) -> float | None:
        values = _outdoor_psychrometrics(self.coordinator)
        return None if values is None else values["vapor_pressure"]


class IndoorOutdoorHumidityDifferenceSensor(VentWiseEntity, SensorEntity):
    """Calculated outdoor-minus-average-indoor absolute humidity."""

    _attr_icon = "mdi:water-sync"
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "indoor_outdoor_humidity_difference", "indoor_outdoor_humidity_difference")

    @property
    def native_value(self) -> float | None:
        return _global_humidity_delta(self.coordinator)


class MoistureExchangeDirectionSensor(VentWiseEntity, SensorEntity):
    """Calculated direction of moisture exchange with outdoor air."""

    _attr_icon = "mdi:water-sync"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "moisture_exchange_direction", "moisture_exchange_direction")

    @property
    def native_value(self) -> str | None:
        return _global_moisture_direction(self.coordinator)


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
        return 0.0 if recommendation is None else round(recommendation.score, 2)


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
        return None if result is None else round(result.candidate_scores.ventilate, 2)


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
        return round(value, 2)


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
        state = self.hass.states.get(self.room.humidity_entity_id)
        value = state_to_float(state)
        source_unit = self.room.humidity_unit or state_unit(state, "%", "humidity")
        normalized, _, reason = normalize_measurement(value, source_unit, "humidity")
        return None if reason is not None else round(normalized, 2)


class RoomIndoorAbsoluteHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Calculated indoor absolute humidity for a room."""

    _attr_icon = "mdi:water-opacity"
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_absolute_humidity", "indoor_absolute_humidity")

    @property
    def native_value(self) -> float | None:
        values = _room_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["absolute"]


class RoomIndoorHumidityRatioSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated indoor humidity ratio for a room."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "g/kg"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_humidity_ratio", "indoor_humidity_ratio")

    @property
    def native_value(self) -> float | None:
        values = _room_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["ratio"]

    @property
    def extra_state_attributes(self) -> dict:
        values = _room_psychrometrics(self.coordinator, self.room)
        return {} if values is None else {"pressure_estimated": values["pressure_estimated"]}


class RoomIndoorVaporPressureSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated indoor water vapor pressure for a room."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "hPa"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_vapor_pressure", "indoor_vapor_pressure")

    @property
    def native_value(self) -> float | None:
        values = _room_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["vapor_pressure"]


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
        value = self.coordinator.data.outdoor_humidity_percent
        return None if value is None else round(value, 2)


class RoomOutdoorAbsoluteHumiditySensor(VentWiseRoomEntity, SensorEntity):
    """Calculated outdoor absolute humidity shown on a room device."""

    _attr_icon = "mdi:water-opacity"
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_absolute_humidity", "outdoor_absolute_humidity")

    @property
    def native_value(self) -> float | None:
        values = _room_outdoor_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["absolute"]


class RoomOutdoorHumidityRatioSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated outdoor humidity ratio shown on a room device."""

    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "g/kg"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_humidity_ratio", "outdoor_humidity_ratio")

    @property
    def native_value(self) -> float | None:
        values = _room_outdoor_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["ratio"]

    @property
    def extra_state_attributes(self) -> dict:
        values = _room_outdoor_psychrometrics(self.coordinator, self.room)
        return {} if values is None else {"pressure_estimated": values["pressure_estimated"]}


class RoomOutdoorVaporPressureSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated outdoor water vapor pressure shown on a room device."""

    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "hPa"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "outdoor_vapor_pressure", "outdoor_vapor_pressure")

    @property
    def native_value(self) -> float | None:
        values = _room_outdoor_psychrometrics(self.coordinator, self.room)
        return None if values is None else values["vapor_pressure"]


class RoomIndoorOutdoorHumidityDifferenceSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated outdoor-minus-indoor absolute humidity for a room."""

    _attr_icon = "mdi:water-sync"
    _attr_native_unit_of_measurement = "g/m³"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "indoor_outdoor_humidity_difference", "indoor_outdoor_humidity_difference")

    @property
    def native_value(self) -> float | None:
        return _room_humidity_delta(self.coordinator, self.room)


class RoomMoistureExchangeDirectionSensor(VentWiseRoomEntity, SensorEntity):
    """Calculated direction of moisture exchange for a room."""

    _attr_icon = "mdi:water-sync"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "moisture_exchange_direction", "moisture_exchange_direction")

    @property
    def native_value(self) -> str | None:
        outdoor = _outdoor_psychrometrics(self.coordinator)
        indoor = _room_psychrometrics(self.coordinator, self.room)
        if outdoor is None or indoor is None:
            return None
        return moisture_exchange_direction(indoor["absolute"], outdoor["absolute"])


class RoomWindSpeedSensor(WindSpeedUnitMixin, VentWiseRoomEntity, SensorEntity):
    """Parsed outdoor wind speed shown on a room device."""

    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator: VentWiseCoordinator, room: RoomConfig) -> None:
        super().__init__(coordinator, room, "wind_speed", "wind_speed")

    @property
    def native_value(self) -> float | None:
        return self._wind_speed(self.coordinator.data.wind_speed_m_s)
