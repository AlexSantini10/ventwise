"""Runtime models and helpers for the integration layer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Callable, Mapping
from datetime import datetime, time, timedelta
from typing import Any
from types import SimpleNamespace

from ..ventwise_core import (
    Availability,
    ComfortObservation,
    ForecastObservation,
    RecommendationAction,
    RecommendationSummary,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    AggregateDecisionResult,
    Observation,
    Validity,
    RoomObservation,
    RoomProfile,
    ScoringConfig,
    ExposureReading,
)

from ..const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_CO2_ENABLED,
    CONF_CO2_ENTITY_ID,
    CONF_CO2_THRESHOLD_PPM,
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_MINIMUM_SCORE,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_NOTIFICATION_ENABLED,
    CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED,
    CONF_DIAGNOSTIC_NOTIFICATION_LEVEL,
    CONF_DEBUG_MODE_ENABLED,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_SOURCE,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_SOURCE,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOM_KIND,
    CONF_ROOM_ENABLED,
    CONF_ROOM_ID,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS,
    CONF_ROOM_NAME,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_START_ENTITY_ID,
    CONF_ROOM_STOP_ENTITY_ID,
    CONF_ROOM_ACTION_CHANGE_HOLD_MINUTES,
    CONF_ROOM_ACTION_LOCKOUT_MINUTES,
    CONF_ROOM_VOLUME_M3,
    CONF_ROOM_OPENING_AREA_M2,
    CONF_ROOM_OPENING_FRACTION,
    CONF_ROOM_EXPOSURE,
    CONF_ROOM_THERMAL_RESISTANCE,
    CONF_ROOM_THERMAL_MASS,
    CONF_ROOMS,
    CONF_RUNTIME_STATE,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_RUNTIME_NOTIFICATION_MARKERS,
    CONF_RUNTIME_ROOM_ACTION_GUARDS,
    CONF_RUNTIME_DIAGNOSTIC_ISSUE,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    CONF_TEMPERATURE_UNIT,
    CONF_WIND_SPEED_UNIT,
    CONF_WIND_SPEED_ENTITY_ID,
    CONF_SMOKE_ALERT_ENTITY_ID,
    CONF_POLLUTION_POLICY,
    CONF_POLLEN_POLICY,
    CONF_OPEN_METEO_AIR_QUALITY_ENABLED,
    CONF_AIR_QUALITY_ENTITY_IDS,
    AIR_QUALITY_VARIABLES,
    CONF_WIND_SPEED_SOURCE,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_CO2_THRESHOLD_PPM,
    DEFAULT_DIAGNOSTIC_NOTIFICATION_LEVEL,
    DEFAULT_DEBUG_MODE_ENABLED,
    DIAGNOSTIC_NOTIFICATION_LEVEL_DIAGNOSTIC,
    DEFAULT_AUTO_COMFORT_TEMPERATURE,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_STABILITY_MINUTES,
    DEFAULT_ROOM_ACTION_CHANGE_HOLD_MINUTES,
    DEFAULT_ROOM_ACTION_LOCKOUT_MINUTES,
    DEFAULT_TARGET_TEMPERATURE_C,
    DEFAULT_TEMPERATURE_UNIT,
    DEFAULT_WIND_SPEED_UNIT,
    OUTDOOR_SOURCE_FORECAST,
    OUTDOOR_SOURCE_OVERRIDE,
)
from ..units import state_unit, temperature_to_celsius, temperature_unit, wind_speed_to_m_s, wind_speed_unit
from ..ventwise_core import ComfortRecommender


@dataclass(frozen=True, slots=True)
class RoomConfig:
    """Serializable room configuration stored in the config entry."""

    room_id: str | None
    name: str
    temperature_entity_id: str
    kind: str = "room"
    enabled: bool = True
    target_temperature_c_override_enabled: bool = False
    target_temperature_c_override: float | None = None
    target_humidity_percent_override_enabled: bool = False
    target_humidity_percent_override: float | None = None
    humidity_entity_id: str | None = None
    co2_entity_id: str | None = None
    window_sensor_entity_ids: tuple[str, ...] = ()
    start_entity_id: str | None = None
    stop_entity_id: str | None = None
    action_change_hold_minutes: int = DEFAULT_ROOM_ACTION_CHANGE_HOLD_MINUTES
    action_lockout_minutes: int = DEFAULT_ROOM_ACTION_LOCKOUT_MINUTES
    volume_m3: float | None = None
    opening_area_m2: float | None = None
    opening_fraction: float | None = None
    exposure: str | None = None
    thermal_resistance_m2k_w: float | None = None
    thermal_mass_kj_k: float | None = None


@dataclass(frozen=True, slots=True)
class IntegrationConfig:
    """Normalised configuration for the integration runtime."""

    outdoor_weather_entity_id: str | None = None
    target_temperature_c: float = DEFAULT_TARGET_TEMPERATURE_C
    temperature_unit: str = DEFAULT_TEMPERATURE_UNIT
    wind_speed_unit: str = DEFAULT_WIND_SPEED_UNIT
    auto_comfort_temperature_enabled: bool = DEFAULT_AUTO_COMFORT_TEMPERATURE
    target_humidity_percent: float = 50.0
    soft_outdoor_threshold_c: float = DEFAULT_SOFT_OUTDOOR_THRESHOLD_C
    minimum_score: float = DEFAULT_MINIMUM_SCORE
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
    stability_minutes: int = DEFAULT_STABILITY_MINUTES
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = DEFAULT_QUIET_HOURS_START
    quiet_hours_end: str = DEFAULT_QUIET_HOURS_END
    enabled: bool = True
    outdoor_temperature_source: str = OUTDOOR_SOURCE_FORECAST
    outdoor_temperature_entity_id: str | None = None
    outdoor_humidity_source: str = OUTDOOR_SOURCE_FORECAST
    outdoor_humidity_entity_id: str | None = None
    wind_speed_source: str = OUTDOOR_SOURCE_FORECAST
    wind_speed_entity_id: str | None = None
    notification_enabled: bool = True
    home_assistant_notification_enabled: bool = False
    diagnostic_notification_level: str = DEFAULT_DIAGNOSTIC_NOTIFICATION_LEVEL
    debug_mode_enabled: bool = DEFAULT_DEBUG_MODE_ENABLED
    co2_enabled: bool = False
    co2_entity_id: str | None = None
    co2_threshold_ppm: float = DEFAULT_CO2_THRESHOLD_PPM
    smoke_alert_entity_id: str | None = None
    pollution_policy: str | None = None
    pollen_policy: str | None = None
    open_meteo_air_quality_enabled: bool = False
    air_quality_entity_ids: Mapping[str, str] = field(default_factory=dict)
    notification_device_ids: tuple[str, ...] = ()
    rooms: tuple[RoomConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Result of a coordinator refresh."""

    summary: RecommendationSummary
    weather_condition: str | None
    target_perceived_c: float | None
    suggested_comfort_temperature_c: float | None
    outdoor_perceived_c: float | None
    active_indoor_perceived_c: float | None
    outdoor_temperature_c: float | None
    forecast_temperature_c: float | None
    outdoor_humidity_percent: float | None
    wind_speed_m_s: float | None
    wind_gust_m_s: float | None
    notification_allowed: bool
    quiet_hours_active: bool
    cooldown_active: bool
    enabled: bool
    stable_for_seconds: int
    last_updated: datetime
    window_states: Mapping[str, str] = field(default_factory=dict)
    # The source-neutral decision artifact is deliberately retained alongside
    # the legacy presentation summary.  This keeps existing entity IDs stable
    # while making every input and decision inspectable.
    decision: Any | None = None


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Persisted runtime markers that should survive restarts."""

    last_action_signature: tuple[str, str] | None = None
    last_action_started_at: datetime | None = None
    notification_markers: Mapping[str, "NotificationMarker"] = field(default_factory=dict)
    room_action_guards: Mapping[str, "RoomActionGuard"] = field(default_factory=dict)
    diagnostic_issue: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationMarker:
    """Last delivered recommendation for one room."""

    signature: tuple[str, str]
    notified_at: datetime
    reason: str | None = None
    severity: str | None = None
    title: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RoomActionGuard:
    """Persisted per-room action transition state."""

    accepted_action: str
    lockout_until: datetime | None = None
    pending_action: str | None = None
    pending_since: datetime | None = None


def build_integration_config(data: Mapping[str, Any]) -> IntegrationConfig:
    """Convert raw config entry data into a runtime config object."""

    rooms = tuple(
        RoomConfig(
            room_id=_string_or_none(room.get(CONF_ROOM_ID)),
            kind=str(room.get(CONF_ROOM_KIND, "room")),
            name=str(room[CONF_ROOM_NAME]),
            temperature_entity_id=str(room[CONF_ROOM_TEMPERATURE_ENTITY_ID]),
            enabled=bool(room.get(CONF_ROOM_ENABLED, True)),
            target_temperature_c_override_enabled=bool(
                room.get(
                    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
                    room.get(CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C) is not None
                    and str(room.get(CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C)).strip() != "",
                )
            ),
            target_temperature_c_override=_float_or_none(
                room.get(CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C)
            ),
            target_humidity_percent_override_enabled=bool(
                room.get(
                    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
                    room.get(CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE) is not None
                    and str(room.get(CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE)).strip() != "",
                )
            ),
            target_humidity_percent_override=_float_or_none(
                room.get(CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE)
            ),
            humidity_entity_id=_string_or_none(room.get(CONF_ROOM_HUMIDITY_ENTITY_ID)),
            co2_entity_id=_string_or_none(room.get(CONF_ROOM_CO2_ENTITY_ID)),
            window_sensor_entity_ids=_string_list(
                room.get(CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS)
            ),
            start_entity_id=_string_or_none(room.get(CONF_ROOM_START_ENTITY_ID)),
            stop_entity_id=_string_or_none(room.get(CONF_ROOM_STOP_ENTITY_ID)),
            action_change_hold_minutes=int(
                room.get(
                    CONF_ROOM_ACTION_CHANGE_HOLD_MINUTES,
                    DEFAULT_ROOM_ACTION_CHANGE_HOLD_MINUTES,
                )
            ),
            action_lockout_minutes=int(
                room.get(
                    CONF_ROOM_ACTION_LOCKOUT_MINUTES,
                    DEFAULT_ROOM_ACTION_LOCKOUT_MINUTES,
                )
            ),
            volume_m3=_float_or_none(room.get(CONF_ROOM_VOLUME_M3)),
            opening_area_m2=_float_or_none(room.get(CONF_ROOM_OPENING_AREA_M2)),
            opening_fraction=_float_or_none(room.get(CONF_ROOM_OPENING_FRACTION)),
            exposure=_string_or_none(room.get(CONF_ROOM_EXPOSURE)),
            thermal_resistance_m2k_w=_float_or_none(room.get(CONF_ROOM_THERMAL_RESISTANCE)),
            thermal_mass_kj_k=_float_or_none(room.get(CONF_ROOM_THERMAL_MASS)),
        )
        for room in data.get(CONF_ROOMS, [])
    )
    return IntegrationConfig(
        outdoor_weather_entity_id=_string_or_none(data.get(CONF_OUTDOOR_WEATHER_ENTITY_ID)),
        target_temperature_c=float(data.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C)),
        temperature_unit=temperature_unit(data.get(CONF_TEMPERATURE_UNIT)),
        wind_speed_unit=wind_speed_unit(data.get(CONF_WIND_SPEED_UNIT)),
        auto_comfort_temperature_enabled=bool(
            data.get(CONF_AUTO_COMFORT_TEMPERATURE, DEFAULT_AUTO_COMFORT_TEMPERATURE)
        ),
        target_humidity_percent=float(data.get(CONF_TARGET_HUMIDITY_PERCENT, 50.0)),
        soft_outdoor_threshold_c=float(
            data.get(CONF_SOFT_OUTDOOR_THRESHOLD_C, DEFAULT_SOFT_OUTDOOR_THRESHOLD_C)
        ),
        minimum_score=float(data.get(CONF_MINIMUM_SCORE, DEFAULT_MINIMUM_SCORE)),
        cooldown_minutes=int(data.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES)),
        stability_minutes=int(data.get(CONF_STABILITY_MINUTES, DEFAULT_STABILITY_MINUTES)),
        quiet_hours_enabled=bool(data.get(CONF_QUIET_HOURS_ENABLED, True)),
        quiet_hours_start=_time_or_default(
            data.get(CONF_QUIET_HOURS_START), DEFAULT_QUIET_HOURS_START
        ),
        quiet_hours_end=_time_or_default(data.get(CONF_QUIET_HOURS_END), DEFAULT_QUIET_HOURS_END),
        enabled=bool(data.get(CONF_ENABLED, True)),
        outdoor_temperature_source=_outdoor_source(
            data,
            CONF_OUTDOOR_TEMPERATURE_SOURCE,
            CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
        ),
        outdoor_temperature_entity_id=_string_or_none(data.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID)),
        outdoor_humidity_source=_outdoor_source(
            data,
            CONF_OUTDOOR_HUMIDITY_SOURCE,
            CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
        ),
        outdoor_humidity_entity_id=_string_or_none(data.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID)),
        wind_speed_source=_outdoor_source(data, CONF_WIND_SPEED_SOURCE, CONF_WIND_SPEED_ENTITY_ID),
        wind_speed_entity_id=_string_or_none(data.get(CONF_WIND_SPEED_ENTITY_ID)),
        notification_enabled=bool(data.get(CONF_NOTIFICATION_ENABLED, True)),
        home_assistant_notification_enabled=bool(
            data.get(CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED, False)
        ),
        diagnostic_notification_level=_diagnostic_notification_level(
            data.get(CONF_DIAGNOSTIC_NOTIFICATION_LEVEL)
        ),
        debug_mode_enabled=bool(data.get(CONF_DEBUG_MODE_ENABLED, DEFAULT_DEBUG_MODE_ENABLED)),
        co2_enabled=bool(data.get(CONF_CO2_ENABLED, False)),
        co2_entity_id=_string_or_none(data.get(CONF_CO2_ENTITY_ID)),
        co2_threshold_ppm=float(data.get(CONF_CO2_THRESHOLD_PPM, DEFAULT_CO2_THRESHOLD_PPM)),
        smoke_alert_entity_id=_string_or_none(data.get(CONF_SMOKE_ALERT_ENTITY_ID)),
        pollution_policy=_exposure_policy(data.get(CONF_POLLUTION_POLICY)),
        pollen_policy=_exposure_policy(data.get(CONF_POLLEN_POLICY)),
        open_meteo_air_quality_enabled=bool(data.get(CONF_OPEN_METEO_AIR_QUALITY_ENABLED, False)),
        air_quality_entity_ids=_air_quality_entity_ids(data.get(CONF_AIR_QUALITY_ENTITY_IDS)),
        notification_device_ids=_string_list(data.get(CONF_NOTIFICATION_DEVICE_ID)),
        rooms=rooms,
    )


def build_scoring_config(config: IntegrationConfig) -> ScoringConfig:
    """Translate integration config into core scoring config."""

    return ScoringConfig(
        target_temperature_c=config.target_temperature_c,
        target_humidity_percent=config.target_humidity_percent,
        soft_outdoor_threshold_c=config.soft_outdoor_threshold_c,
        minimum_score=config.minimum_score,
        minimum_stability_seconds=config.stability_minutes * 60,
        co2_enabled=config.co2_enabled,
        co2_threshold_ppm=config.co2_threshold_ppm,
    )


def load_runtime_state(data: Mapping[str, Any]) -> RuntimeState:
    """Load persisted runtime markers from stored config entry data."""

    raw_state = data.get(CONF_RUNTIME_STATE)
    if not isinstance(raw_state, Mapping):
        return RuntimeState()
    notification_markers = _load_notification_markers(
        raw_state.get(CONF_RUNTIME_NOTIFICATION_MARKERS)
    )
    room_action_guards = _load_room_action_guards(raw_state.get(CONF_RUNTIME_ROOM_ACTION_GUARDS))
    if not notification_markers:
        legacy_signature = _load_signature(raw_state.get(CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE))
        legacy_notified_at = _load_datetime(raw_state.get(CONF_RUNTIME_LAST_NOTIFICATION_AT))
        if legacy_signature is not None and legacy_notified_at is not None and legacy_signature[1]:
            notification_markers = {
                legacy_signature[1]: NotificationMarker(legacy_signature, legacy_notified_at)
            }

    return RuntimeState(
        last_action_signature=_load_signature(raw_state.get(CONF_RUNTIME_LAST_ACTION_SIGNATURE)),
        last_action_started_at=_load_datetime(raw_state.get(CONF_RUNTIME_LAST_ACTION_STARTED_AT)),
        notification_markers=notification_markers,
        room_action_guards=room_action_guards,
        diagnostic_issue=_string_or_none(raw_state.get(CONF_RUNTIME_DIAGNOSTIC_ISSUE)),
    )


def dump_runtime_state(state: RuntimeState) -> dict[str, Any]:
    """Serialize persisted runtime markers for storage in the config entry."""

    return {
        CONF_RUNTIME_STATE: {
            CONF_RUNTIME_LAST_ACTION_SIGNATURE: list(state.last_action_signature)
            if state.last_action_signature is not None
            else None,
            CONF_RUNTIME_LAST_ACTION_STARTED_AT: _dump_datetime(state.last_action_started_at),
            CONF_RUNTIME_NOTIFICATION_MARKERS: {
                room_name: {
                    "signature": list(marker.signature),
                    "notified_at": _dump_datetime(marker.notified_at),
                    **({"reason": marker.reason} if marker.reason is not None else {}),
                    **({"severity": marker.severity} if marker.severity is not None else {}),
                    **({"title": marker.title} if marker.title is not None else {}),
                    **({"message": marker.message} if marker.message is not None else {}),
                }
                for room_name, marker in state.notification_markers.items()
            },
            CONF_RUNTIME_ROOM_ACTION_GUARDS: {
                room_key: {
                    "accepted_action": guard.accepted_action,
                    **({"lockout_until": _dump_datetime(guard.lockout_until)} if guard.lockout_until else {}),
                    **({"pending_action": guard.pending_action} if guard.pending_action else {}),
                    **({"pending_since": _dump_datetime(guard.pending_since)} if guard.pending_since else {}),
                }
                for room_key, guard in state.room_action_guards.items()
            },
            CONF_RUNTIME_DIAGNOSTIC_ISSUE: state.diagnostic_issue,
        }
    }


def state_to_float(state: Any | None) -> float | None:
    """Convert a Home Assistant state into a float when possible."""

    raw_state = getattr(state, "state", None)
    if raw_state is None or raw_state in {"unknown", "unavailable", ""}:
        return None
    try:
        return float(raw_state)
    except (TypeError, ValueError):
        return None


def state_to_bool(state: Any | None) -> bool | None:
    """Convert a Home Assistant state into a boolean when possible."""

    raw_state = getattr(state, "state", None)
    if raw_state is None or raw_state in {"unknown", "unavailable", ""}:
        return None
    lowered = str(raw_state).lower()
    if lowered in {"on", "true", "1", "home", "open"}:
        return True
    if lowered in {"off", "false", "0", "closed", "not_home"}:
        return False
    return None


def observation_from_state(
    state: Any | None,
    *,
    source_id: str | None,
    now: datetime,
    unit: str,
    value: Any = None,
    converter: Callable[[Any, Any], Any] | None = None,
) -> Observation[Any]:
    """Adapt one HA state without inventing a value or timestamp.

    ``last_updated`` is HA's measurement provenance for this adapter; test
    doubles without it use the receipt instant only so legacy fixtures remain
    usable.  Unavailable and malformed states stay explicit in the snapshot.
    """

    received_at = now
    observed_at = getattr(state, "last_updated", None) if state is not None else None
    if observed_at is None and state is not None:
        observed_at = received_at
    raw = getattr(state, "state", None) if value is None else value
    if state is None:
        return Observation(None, unit, None, received_at, source_id, availability=Availability.AWAITING_SOURCE)
    if raw is None or str(raw).strip().lower() in {"", "unknown", "unavailable", "none"}:
        return Observation(None, unit, observed_at, received_at, source_id, availability=Availability.MISSING)
    try:
        canonical = converter(raw, state) if converter else raw
    except (TypeError, ValueError):
        return Observation(None, unit, observed_at, received_at, source_id, validity=Validity.INVALID, availability=Availability.INVALID)
    if canonical is None:
        return Observation(None, unit, observed_at, received_at, source_id, validity=Validity.INVALID, availability=Availability.INVALID)
    return Observation(canonical, unit, observed_at, received_at, source_id)


def build_decision_snapshot(
    config: IntegrationConfig,
    state_getter: Callable[[str], Any],
    now: datetime,
    *,
    forecast: ForecastObservation | None = None,
    co2_history: dict[str, list[tuple[datetime, float]]] | None = None,
    provider_exposure: Mapping[str, Any] | None = None,
) -> DecisionSnapshot:
    """Create the complete immutable decision input from configured HA state.

    No fallback defaults are used: required inputs that cannot be observed are
    represented as unavailable observations, which causes the engine to fail
    closed for opening/ventilation advice.
    """

    def weather_attribute(attribute: str, unit: str, converter=None) -> Observation[Any]:
        weather_id = config.outdoor_weather_entity_id
        weather = state_getter(weather_id) if weather_id else None
        attrs = getattr(weather, "attributes", {}) or {}
        if weather is None or attribute not in attrs:
            observed_at = getattr(weather, "last_updated", None) if weather is not None else None
            return Observation(None, unit, observed_at, now, weather_id, availability=Availability.AWAITING_SOURCE if weather is None else Availability.MISSING)
        return observation_from_state(weather, source_id=weather_id, now=now, unit=unit,
            value=attrs.get(attribute), converter=converter)

    def selected_numeric(source: str, entity_id: str | None, attribute: str, unit: str, measurement: str | None = None) -> Observation[float]:
        if source == OUTDOOR_SOURCE_OVERRIDE and entity_id:
            state = state_getter(entity_id)
            return observation_from_state(state, source_id=entity_id, now=now, unit=unit,
                converter=lambda raw, item: _canonical_measurement_value(float(raw), item, measurement))
        return weather_attribute(attribute, unit, lambda raw, item: _canonical_measurement_value(float(raw), item, measurement))

    temperature = selected_numeric(config.outdoor_temperature_source, config.outdoor_temperature_entity_id, "temperature", "°C", "temperature")
    humidity = selected_numeric(config.outdoor_humidity_source, config.outdoor_humidity_entity_id, "humidity", "%")
    wind = selected_numeric(config.wind_speed_source, config.wind_speed_entity_id, "wind_speed", "m/s", "wind_speed")
    gust = weather_attribute("wind_gust_speed", "m/s", lambda raw, item: _canonical_measurement_value(float(raw), item, "wind_speed"))
    weather_state = state_getter(config.outdoor_weather_entity_id) if config.outdoor_weather_entity_id else None
    condition = observation_from_state(weather_state, source_id=config.outdoor_weather_entity_id, now=now, unit="", converter=lambda raw, _: str(raw).lower())
    rain = weather_attribute("precipitation_probability", "%", lambda raw, _: float(raw))
    forecast_temp = Observation(
        forecast.temperature_c if forecast and forecast.temperature_c is not None else None,
        "°C", now if forecast and forecast.temperature_c is not None else None, now,
        "weather.forecast", availability=Availability.AVAILABLE if forecast and forecast.temperature_c is not None else Availability.AWAITING_SOURCE,
    )

    rooms: list[DecisionRoom] = []
    history = co2_history if co2_history is not None else {}
    for room in config.rooms:
        room_key = room.room_id or room.name
        temp_state = state_getter(room.temperature_entity_id)
        room_temp = observation_from_state(temp_state, source_id=room.temperature_entity_id, now=now, unit="°C",
            converter=lambda raw, item: _canonical_measurement_value(float(raw), item, "temperature"))
        humidity_state = state_getter(room.humidity_entity_id) if room.humidity_entity_id else None
        room_humidity = observation_from_state(humidity_state, source_id=room.humidity_entity_id, now=now, unit="%", converter=lambda raw, _: float(raw))
        co2_id = room.co2_entity_id or config.co2_entity_id
        co2_state = state_getter(co2_id) if config.co2_enabled and co2_id else None
        co2 = observation_from_state(co2_state, source_id=co2_id, now=now, unit="ppm", converter=lambda raw, _: float(raw)) if co2_id and config.co2_enabled else None
        trend: Observation[float] | None = None
        if co2 is not None and co2.value is not None and co2.observed_at is not None:
            samples = [(at, val) for at, val in history.get(room_key, []) if now - at <= timedelta(minutes=30)]
            if not samples or samples[-1] != (co2.observed_at, co2.value):
                samples.append((co2.observed_at, co2.value))
            history[room_key] = samples
            first_at, first_value = samples[0]
            seconds = (co2.observed_at - first_at).total_seconds()
            if len(samples) >= 2 and seconds >= 300:
                trend = Observation((co2.value - first_value) * 3600 / seconds, "ppm/h", co2.observed_at, now, co2_id)
            else:
                trend = Observation(None, "ppm/h", co2.observed_at, now, co2_id, availability=Availability.AWAITING_SOURCE)
        contacts = [state_to_bool(state_getter(entity)) for entity in room.window_sensor_entity_ids]
        window = None
        if contacts:
            value = True if any(item is True for item in contacts) else (False if all(item is False for item in contacts) else None)
            window = Observation(value, "", now, now, ",".join(room.window_sensor_entity_ids), availability=Availability.AVAILABLE if value is not None else Availability.MISSING)
        rooms.append(DecisionRoom(room_key, room.name, room_temp, room_humidity, co2, trend, window,
            room.target_temperature_c_override if room.target_temperature_c_override_enabled else config.target_temperature_c,
            room.target_humidity_percent_override if room.target_humidity_percent_override_enabled else config.target_humidity_percent))
    smoke_state = state_getter(config.smoke_alert_entity_id) if config.smoke_alert_entity_id else None
    smoke = observation_from_state(smoke_state, source_id=config.smoke_alert_entity_id, now=now, unit="", converter=lambda raw, _: state_to_bool(SimpleNamespace(state=raw))) if config.smoke_alert_entity_id else None
    policy_source = "user_policy"
    pollen_policy = Observation(config.pollen_policy, "", now, now, policy_source) if config.pollen_policy else None
    pollution_policy = Observation(config.pollution_policy, "", now, now, policy_source) if config.pollution_policy else None
    exposure: list[ExposureReading] = []
    # Configured HA entities are authoritative. The provider is only allowed
    # to fill a named field for which no HA entity was configured.
    for kind in AIR_QUALITY_VARIABLES:
        entity_id = config.air_quality_entity_ids.get(kind)
        if entity_id:
            state = state_getter(entity_id)
            attributes = getattr(state, "attributes", {}) or {}
            unit = str(attributes.get("unit_of_measurement", ""))
            observation = observation_from_state(state, source_id=entity_id, now=now, unit=unit, converter=lambda raw, _: float(raw))
            exposure.append(ExposureReading(kind, observation, str(attributes.get("averaging_period", "instant"))))
        elif provider_exposure and provider_exposure.get(kind) is not None:
            item = provider_exposure[kind]
            exposure.append(ExposureReading(kind, item.observation, item.averaging_period, item.attribution, item.resolution, item.coverage))
    return DecisionSnapshot(tuple(rooms), DecisionOutdoor(temperature, humidity, wind, gust, condition, rain, forecast_temp, smoke, pollen_policy, pollution_policy, tuple(exposure)), now)


def is_quiet_hours_active(now: datetime, start_time: str, end_time: str) -> bool:
    """Check whether the current local time falls inside quiet hours."""

    current = now.time()
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def build_room_profiles(
    config: IntegrationConfig,
    state_getter: Callable[[str], Any],
    forecast_temperature_c: float | None = None,
    forecast: ForecastObservation | None = None,
) -> tuple[list[RoomProfile], ComfortObservation | None]:
    """Build room profiles and the outdoor observation from Home Assistant state."""

    outdoor_temp = _outdoor_value(
        config.outdoor_temperature_source,
        config.outdoor_weather_entity_id,
        config.outdoor_temperature_entity_id,
        state_getter,
        "temperature",
        measurement="temperature",
    )
    outdoor_humidity = _outdoor_value(
        config.outdoor_humidity_source,
        config.outdoor_weather_entity_id,
        config.outdoor_humidity_entity_id,
        state_getter,
        "humidity",
        allow_state_fallback=False,
    )
    if outdoor_temp is None:
        outdoor = None
    else:
        if outdoor_humidity is None:
            outdoor_humidity = 50.0
        weather_condition = _weather_condition(
            config.outdoor_weather_entity_id,
            state_getter,
        )
        wind_speed = _outdoor_value(
            config.wind_speed_source,
            config.outdoor_weather_entity_id,
            config.wind_speed_entity_id,
            state_getter,
            "wind_speed",
            allow_state_fallback=False,
            measurement="wind_speed",
        )
        wind_gust = _weather_gust_value(
            config.outdoor_weather_entity_id,
            state_getter,
        )
        outdoor = ComfortObservation(
            temperature_c=outdoor_temp,
            humidity_percent=outdoor_humidity,
            wind_speed_m_s=wind_speed,
            wind_gust_m_s=wind_gust,
            weather_condition=weather_condition,
            forecast_temperature_c=forecast_temperature_c,
            forecast=forecast,
        )

    rooms: list[RoomProfile] = []
    for room in config.rooms:
        temperature = state_to_temperature_c(state_getter(room.temperature_entity_id))
        humidity = state_to_float(state_getter(room.humidity_entity_id)) if room.humidity_entity_id else None
        co2 = state_to_float(state_getter(room.co2_entity_id or config.co2_entity_id)) if config.co2_enabled and (room.co2_entity_id or config.co2_entity_id) else None
        if temperature is None:
            continue
        if humidity is None:
            humidity = 50.0
        rooms.append(
            RoomProfile(
                room_id=room.room_id,
                name=room.name,
                indoor=RoomObservation(
                    temperature_c=temperature,
                    humidity_percent=humidity,
                ),
                kind=room.kind,
                enabled=room.enabled,
                target_temperature_c_override_enabled=room.target_temperature_c_override_enabled,
                target_temperature_c_override=room.target_temperature_c_override,
                target_humidity_percent_override_enabled=room.target_humidity_percent_override_enabled,
                target_humidity_percent_override=room.target_humidity_percent_override,
                co2_ppm=co2,
            )
        )

    return rooms, outdoor


WINDOW_STATE_NOT_CONFIGURED = "not_configured"
WINDOW_STATE_OPEN = "open"
WINDOW_STATE_CLOSED = "closed"
WINDOW_STATE_UNAVAILABLE = "unavailable"


def room_window_states(
    config: IntegrationConfig,
    state_getter: Callable[[str], Any],
) -> dict[str, str]:
    """Aggregate each room's optional contact sensors without scoring them."""

    return {
        room.room_id or room.name: room_window_state(room, state_getter)
        for room in config.rooms
    }


def room_window_state(room: RoomConfig, state_getter: Callable[[str], Any]) -> str:
    """Return open when any contact is open, closed only when all are closed."""

    if not room.window_sensor_entity_ids:
        return WINDOW_STATE_NOT_CONFIGURED
    states = [
        state_to_bool(state_getter(entity_id))
        for entity_id in room.window_sensor_entity_ids
    ]
    if any(state is True for state in states):
        return WINDOW_STATE_OPEN
    if all(state is False for state in states):
        return WINDOW_STATE_CLOSED
    return WINDOW_STATE_UNAVAILABLE


def gate_room_recommendations(
    summary: RecommendationSummary,
    window_states: Mapping[str, str],
) -> RecommendationSummary:
    """Suppress advice already satisfied by a configured room window state."""

    gated_recommendations = []
    gated_any = False
    for recommendation in summary.room_recommendations:
        window_state = window_states.get(
            recommendation.room_id or recommendation.room_name,
            WINDOW_STATE_NOT_CONFIGURED,
        )
        action = recommendation.action
        if window_state == WINDOW_STATE_OPEN and action in {
            RecommendationAction.OPEN,
            RecommendationAction.VENTILATE,
        }:
            gated_recommendations.append(
                replace(
                    recommendation,
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="The room windows are already open.",
                    reason_code="window_already_open",
                )
            )
            gated_any = True
        elif window_state == WINDOW_STATE_CLOSED and action == RecommendationAction.CLOSE:
            gated_recommendations.append(
                replace(
                    recommendation,
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="The room windows are already closed.",
                    reason_code="window_already_closed",
                )
            )
            gated_any = True
        else:
            gated_recommendations.append(recommendation)

    if not gated_any:
        return summary
    actionable = [
        recommendation
        for recommendation in gated_recommendations
        if recommendation.action != RecommendationAction.NONE
    ]
    if not actionable:
        return replace(
            summary,
            action=RecommendationAction.NONE,
            score=0.0,
            reason="The configured room window states already match the advice.",
            blocked_by="window_state",
            best_room=None,
            room_recommendations=tuple(gated_recommendations),
        )
    best = max(actionable, key=lambda recommendation: recommendation.score)
    return replace(
        summary,
        action=best.action,
        score=best.score,
        reason=best.reason,
        best_room=best.room_name,
        room_recommendations=tuple(gated_recommendations),
    )


def build_debug_attributes(
    config: IntegrationConfig,
    snapshot: RuntimeSnapshot,
) -> dict[str, Any]:
    """Build user-friendly debug attributes for VentWise entities."""

    summary = snapshot.summary
    room_details = [
        _room_debug_attributes(room, recommendation, snapshot.window_states)
        for room, recommendation in zip(config.rooms, summary.room_recommendations)
    ]
    best_room_details = next(
        (details for details in room_details if details["room_name"] == summary.best_room),
        None,
    )
    return {
        "summary_action": summary.action.value,
        "summary_score": summary.score,
        "summary_reason": summary.reason,
        "summary_best_room": summary.best_room,
        "summary_blocked_by": summary.blocked_by,
        "summary_suggested_comfort_temperature_c": summary.suggested_comfort_temperature_c,
        "weather_condition": snapshot.weather_condition,
        "target_perceived_c": snapshot.target_perceived_c,
        "suggested_comfort_temperature_c": snapshot.suggested_comfort_temperature_c,
        "outdoor_perceived_c": snapshot.outdoor_perceived_c,
        "active_indoor_perceived_c": snapshot.active_indoor_perceived_c,
        "notification_enabled": config.notification_enabled,
        "notification_allowed": snapshot.notification_allowed,
        "quiet_hours_active": snapshot.quiet_hours_active,
        "cooldown_active": snapshot.cooldown_active,
        "stable_for_seconds": snapshot.stable_for_seconds,
        "outdoor_temperature_c": snapshot.outdoor_temperature_c,
        "forecast_temperature_c": snapshot.forecast_temperature_c,
        "co2_enabled": config.co2_enabled,
        "co2_threshold_ppm": config.co2_threshold_ppm,
        "outdoor_humidity_percent": snapshot.outdoor_humidity_percent,
        "wind_speed_m_s": snapshot.wind_speed_m_s,
        "wind_gust_m_s": snapshot.wind_gust_m_s,
        "target_temperature_c": config.target_temperature_c,
        "temperature_unit": config.temperature_unit,
        "wind_speed_unit": config.wind_speed_unit,
        "auto_comfort_temperature_enabled": config.auto_comfort_temperature_enabled,
        "target_humidity_percent": config.target_humidity_percent,
        "soft_outdoor_threshold_c": config.soft_outdoor_threshold_c,
        "minimum_score": config.minimum_score,
        "stability_minutes": config.stability_minutes,
        "cooldown_minutes": config.cooldown_minutes,
        "quiet_hours_enabled": config.quiet_hours_enabled,
        "room_recommendations": room_details,
        "best_room_recommendation": best_room_details,
        "decision": _decision_debug_attributes(snapshot.decision),
    }


def apply_decision_to_summary(
    summary: RecommendationSummary,
    decision: AggregateDecisionResult,
) -> RecommendationSummary:
    """Project the deterministic decision onto stable legacy entity models."""

    by_id = {result.room_id: result for result in decision.room_results}
    recommendations = []
    for recommendation in summary.room_recommendations:
        result = by_id.get(recommendation.room_id or recommendation.room_name)
        if result is None:
            recommendations.append(recommendation)
            continue
        score = max(result.candidate_scores.open, result.candidate_scores.ventilate, result.candidate_scores.close)
        recommendations.append(replace(
            recommendation,
            action=result.delivered_action,
            score=score if result.delivered_action != RecommendationAction.NONE else 0.0,
            reason=result.reason_code,
            reason_code=result.reason_code,
            ventilation_duration_minutes=result.duration_minutes,
        ))
    actionable = [item for item in recommendations if item.action != RecommendationAction.NONE]
    if not actionable:
        return replace(summary, action=RecommendationAction.NONE, score=0.0,
            reason="No actionable deterministic recommendation.", blocked_by="decision", best_room=None,
            room_recommendations=tuple(recommendations))
    best = max(actionable, key=lambda item: item.score)
    return replace(summary, action=best.action, score=best.score, reason=best.reason,
        best_room=best.room_name, blocked_by=None, room_recommendations=tuple(recommendations))


def _decision_debug_attributes(decision: AggregateDecisionResult | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "core_action": decision.core_action.value,
        "delivered_action": decision.delivered_action.value,
        "trace": [{"code": item.code, "detail": item.detail} for item in decision.trace],
        "rooms": [
            {
                "room_id": item.room_id,
                "core_action": item.core_action.value,
                "delivered_action": item.delivered_action.value,
                "duration_minutes": item.duration_minutes,
                "candidates": {"open": item.candidate_scores.open, "ventilate": item.candidate_scores.ventilate, "close": item.candidate_scores.close},
                "trace": [{"code": trace.code, "detail": trace.detail} for trace in item.trace],
                "blocked_conditions": list(item.blocked_conditions),
                "applied_penalties": list(item.applied_penalties),
                "data_quality": {"used": list(item.data_quality.used), "discarded": list(item.data_quality.discarded), "awaiting_source": list(item.data_quality.awaiting_source)},
                "delivery_suppressed_by": item.delivery_suppressed_by,
            }
            for item in decision.room_results
        ],
    }


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _time_or_default(value: Any, default: str) -> str:
    """Convert a saved quiet-hours value into a safe HH:MM[:SS] string."""

    if value is None:
        return default
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    text = str(value).strip()
    if not text:
        return default
    try:
        parsed = _parse_time(text)
    except ValueError:
        return default
    return parsed.strftime("%H:%M:%S")


def _string_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return tuple(items)
    text = str(value).strip()
    return (text,) if text else ()


def _diagnostic_notification_level(value: Any) -> str:
    """Return a supported diagnostic notification level."""

    return (
        DIAGNOSTIC_NOTIFICATION_LEVEL_DIAGNOSTIC
        if value == DIAGNOSTIC_NOTIFICATION_LEVEL_DIAGNOSTIC
        else DEFAULT_DIAGNOSTIC_NOTIFICATION_LEVEL
    )


def _exposure_policy(value: Any) -> str | None:
    """Keep exposure advisory until the user selects reduce or avoid."""

    text = _string_or_none(value)
    return text if text in {"reduce", "avoid"} else None


def _air_quality_entity_ids(value: Any) -> Mapping[str, str]:
    """Accept known HA source keys without retaining provider location data."""

    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): entity_id
        for key, raw in value.items()
        if str(key) in AIR_QUALITY_VARIABLES
        and (entity_id := _string_or_none(raw)) is not None
    }


def _outdoor_value(
    source: str,
    weather_entity_id: str | None,
    override_entity_id: str | None,
    state_getter: Callable[[str], Any],
    attribute_name: str,
    *,
    allow_state_fallback: bool = True,
    measurement: str | None = None,
) -> float | None:
    if source == OUTDOOR_SOURCE_OVERRIDE and override_entity_id:
        state = state_getter(override_entity_id)
        return _canonical_measurement_value(state_to_float(state), state, measurement)
    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    value = attributes.get(attribute_name)
    if value is None:
        if not allow_state_fallback:
            return None
        return _canonical_measurement_value(state_to_float(state), state, measurement)
    try:
        return _canonical_measurement_value(float(value), state, measurement)
    except (TypeError, ValueError):
        return None


def state_to_temperature_c(state: Any | None) -> float | None:
    """Read a state temperature using its declared Home Assistant unit."""
    return _canonical_measurement_value(state_to_float(state), state, "temperature")


def _canonical_measurement_value(value: float | None, state: Any | None, measurement: str | None) -> float | None:
    if value is None:
        return None
    if measurement == "temperature":
        return temperature_to_celsius(value, state_unit(state, DEFAULT_TEMPERATURE_UNIT, "temperature"))
    if measurement == "wind_speed":
        return wind_speed_to_m_s(value, state_unit(state, DEFAULT_WIND_SPEED_UNIT, "wind_speed"))
    return value


def _outdoor_source(data: Mapping[str, Any], source_key: str, entity_key: str) -> str:
    source = data.get(source_key)
    if source in {OUTDOOR_SOURCE_FORECAST, OUTDOOR_SOURCE_OVERRIDE}:
        return str(source)
    entity = _string_or_none(data.get(entity_key))
    if entity is not None:
        return OUTDOOR_SOURCE_OVERRIDE
    return OUTDOOR_SOURCE_FORECAST


def _parse_time(value: str) -> time:
    text = value.strip()
    if len(text.split(":")) == 2:
        return datetime.strptime(text, "%H:%M").time()
    return datetime.strptime(text, "%H:%M:%S").time()


def _load_signature(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    first, second = value
    return str(first), str(second)


def _load_notification_markers(value: Any) -> dict[str, NotificationMarker]:
    """Load valid per-room notification markers from persisted data."""

    if not isinstance(value, Mapping):
        return {}
    markers: dict[str, NotificationMarker] = {}
    for room_name, raw_marker in value.items():
        if not isinstance(room_name, str) or not room_name.strip() or not isinstance(raw_marker, Mapping):
            continue
        signature = _load_signature(raw_marker.get("signature"))
        notified_at = _load_datetime(raw_marker.get("notified_at"))
        if signature is not None and notified_at is not None:
            markers[room_name] = NotificationMarker(
                signature,
                notified_at,
                _string_or_none(raw_marker.get("reason")),
                _string_or_none(raw_marker.get("severity")),
                _string_or_none(raw_marker.get("title")),
                _string_or_none(raw_marker.get("message")),
            )
    return markers


def _load_room_action_guards(value: Any) -> dict[str, RoomActionGuard]:
    """Load valid per-room action guardrails from persisted data."""

    if not isinstance(value, Mapping):
        return {}
    guards: dict[str, RoomActionGuard] = {}
    for room_key, raw_guard in value.items():
        if not isinstance(room_key, str) or not room_key.strip() or not isinstance(raw_guard, Mapping):
            continue
        accepted_action = raw_guard.get("accepted_action")
        if accepted_action not in {"open", "ventilate", "close"}:
            continue
        pending_action = raw_guard.get("pending_action")
        if pending_action not in {"open", "ventilate", "close"}:
            pending_action = None
        guards[room_key] = RoomActionGuard(
            accepted_action,
            _load_datetime(raw_guard.get("lockout_until")),
            pending_action,
            _load_datetime(raw_guard.get("pending_since")),
        )
    return guards


def _load_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _dump_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _room_debug_attributes(
    room: RoomProfile,
    recommendation: RoomRecommendation,
    window_states: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "room_name": room.name,
        "kind": room.kind,
        "action": recommendation.action.value,
        "score": recommendation.score,
        "reason": recommendation.reason,
        "indoor_perceived_c": recommendation.indoor_perceived_c,
        "outdoor_perceived_c": recommendation.outdoor_perceived_c,
        "suggested_comfort_temperature_c": recommendation.suggested_comfort_temperature_c,
        "open_score": recommendation.open_score,
        "close_score": recommendation.close_score,
        "ventilation_duration_minutes": recommendation.ventilation_duration_minutes,
        "indoor_comfort_severity": recommendation.indoor_comfort_severity,
        "outdoor_comfort_severity": recommendation.outdoor_comfort_severity,
        "co2_ppm": recommendation.co2_ppm,
        "co2_influence": recommendation.co2_influence,
        "window_state": (window_states or {}).get(
            room.room_id or room.name, WINDOW_STATE_NOT_CONFIGURED
        ),
    }


def _weather_condition(
    weather_entity_id: str | None,
    state_getter: Callable[[str], Any],
) -> str | None:
    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    raw_state = getattr(state, "state", None)
    if raw_state is None:
        return None
    text = str(raw_state).strip()
    return text or None


def _weather_gust_value(
    weather_entity_id: str | None,
    state_getter: Callable[[str], Any],
) -> float | None:
    """Extract a wind gust value from a weather entity when available."""

    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    for key in ("wind_gust_speed", "wind_gust_m_s", "wind_gust"):
        value = attributes.get(key)
        if value is None:
            continue
        try:
            return wind_speed_to_m_s(float(value), state_unit(state, DEFAULT_WIND_SPEED_UNIT, "wind_speed"))
        except (TypeError, ValueError):
            continue
    return None


def find_room_recommendation(
    summary: RecommendationSummary,
    room: RoomConfig,
) -> Any | None:
    """Find the recommendation matching a room config."""

    for recommendation in summary.room_recommendations:
        if recommendation.room_id is not None and room.room_id is not None:
            if recommendation.room_id == room.room_id:
                return recommendation
        if recommendation.room_id is None and recommendation.room_name == room.name:
                return recommendation
    return None


def room_target_temperature_c(
    room: RoomConfig,
    config: IntegrationConfig,
) -> float:
    """Return the effective comfort temperature for a room."""

    if room.target_temperature_c_override_enabled and room.target_temperature_c_override is not None:
        return room.target_temperature_c_override
    return config.target_temperature_c
