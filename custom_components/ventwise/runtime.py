"""Runtime models and helpers for the integration layer."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from datetime import datetime, time
from typing import Any

from .ventwise_core import (
    ComfortObservation,
    RecommendationSummary,
    RoomObservation,
    RoomProfile,
    ScoringConfig,
)

from .const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_MINIMUM_SCORE,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_NOTIFICATION_ENABLED,
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
    CONF_ROOM_NAME,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_START_ENTITY_ID,
    CONF_ROOM_STOP_ENTITY_ID,
    CONF_ROOMS,
    CONF_RUNTIME_STATE,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    CONF_WIND_SPEED_ENTITY_ID,
    CONF_WIND_SPEED_SOURCE,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_AUTO_COMFORT_TEMPERATURE,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_STABILITY_MINUTES,
    DEFAULT_TARGET_TEMPERATURE_C,
    OUTDOOR_SOURCE_FORECAST,
    OUTDOOR_SOURCE_OVERRIDE,
)
from .ventwise_core import ComfortRecommender


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
    start_entity_id: str | None = None
    stop_entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class IntegrationConfig:
    """Normalised configuration for the integration runtime."""

    outdoor_weather_entity_id: str | None = None
    target_temperature_c: float = DEFAULT_TARGET_TEMPERATURE_C
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
    outdoor_humidity_percent: float | None
    wind_speed_m_s: float | None
    notification_allowed: bool
    quiet_hours_active: bool
    cooldown_active: bool
    enabled: bool
    stable_for_seconds: int
    last_updated: datetime


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Persisted runtime markers that should survive restarts."""

    last_action_signature: tuple[str, str] | None = None
    last_action_started_at: datetime | None = None
    last_notification_signature: tuple[str, str] | None = None
    last_notification_at: datetime | None = None


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
            start_entity_id=_string_or_none(room.get(CONF_ROOM_START_ENTITY_ID)),
            stop_entity_id=_string_or_none(room.get(CONF_ROOM_STOP_ENTITY_ID)),
        )
        for room in data.get(CONF_ROOMS, [])
    )
    return IntegrationConfig(
        outdoor_weather_entity_id=_string_or_none(data.get(CONF_OUTDOOR_WEATHER_ENTITY_ID)),
        target_temperature_c=float(data.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C)),
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
    )


def load_runtime_state(data: Mapping[str, Any]) -> RuntimeState:
    """Load persisted runtime markers from stored config entry data."""

    raw_state = data.get(CONF_RUNTIME_STATE)
    if not isinstance(raw_state, Mapping):
        return RuntimeState()
    return RuntimeState(
        last_action_signature=_load_signature(raw_state.get(CONF_RUNTIME_LAST_ACTION_SIGNATURE)),
        last_action_started_at=_load_datetime(raw_state.get(CONF_RUNTIME_LAST_ACTION_STARTED_AT)),
        last_notification_signature=_load_signature(
            raw_state.get(CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE)
        ),
        last_notification_at=_load_datetime(raw_state.get(CONF_RUNTIME_LAST_NOTIFICATION_AT)),
    )


def dump_runtime_state(state: RuntimeState) -> dict[str, Any]:
    """Serialize persisted runtime markers for storage in the config entry."""

    return {
        CONF_RUNTIME_STATE: {
            CONF_RUNTIME_LAST_ACTION_SIGNATURE: list(state.last_action_signature)
            if state.last_action_signature is not None
            else None,
            CONF_RUNTIME_LAST_ACTION_STARTED_AT: _dump_datetime(state.last_action_started_at),
            CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: list(state.last_notification_signature)
            if state.last_notification_signature is not None
            else None,
            CONF_RUNTIME_LAST_NOTIFICATION_AT: _dump_datetime(state.last_notification_at),
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
) -> tuple[list[RoomProfile], ComfortObservation | None]:
    """Build room profiles and the outdoor observation from Home Assistant state."""

    outdoor_temp = _outdoor_value(
        config.outdoor_temperature_source,
        config.outdoor_weather_entity_id,
        config.outdoor_temperature_entity_id,
        state_getter,
        "temperature",
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
        )
        outdoor = ComfortObservation(
            temperature_c=outdoor_temp,
            humidity_percent=outdoor_humidity,
            wind_speed_m_s=wind_speed,
            weather_condition=weather_condition,
        )

    rooms: list[RoomProfile] = []
    for room in config.rooms:
        temperature = state_to_float(state_getter(room.temperature_entity_id))
        humidity = state_to_float(state_getter(room.humidity_entity_id)) if room.humidity_entity_id else None
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
            )
        )

    return rooms, outdoor


def build_debug_attributes(
    config: IntegrationConfig,
    snapshot: RuntimeSnapshot,
) -> dict[str, Any]:
    """Build user-friendly debug attributes for VentWise entities."""

    summary = snapshot.summary
    room_details = [
        _room_debug_attributes(room, recommendation)
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
        "outdoor_humidity_percent": snapshot.outdoor_humidity_percent,
        "wind_speed_m_s": snapshot.wind_speed_m_s,
        "target_temperature_c": config.target_temperature_c,
        "auto_comfort_temperature_enabled": config.auto_comfort_temperature_enabled,
        "target_humidity_percent": config.target_humidity_percent,
        "soft_outdoor_threshold_c": config.soft_outdoor_threshold_c,
        "minimum_score": config.minimum_score,
        "stability_minutes": config.stability_minutes,
        "cooldown_minutes": config.cooldown_minutes,
        "quiet_hours_enabled": config.quiet_hours_enabled,
        "room_recommendations": room_details,
        "best_room_recommendation": best_room_details,
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


def _outdoor_value(
    source: str,
    weather_entity_id: str | None,
    override_entity_id: str | None,
    state_getter: Callable[[str], Any],
    attribute_name: str,
    *,
    allow_state_fallback: bool = True,
) -> float | None:
    if source == OUTDOOR_SOURCE_OVERRIDE and override_entity_id:
        return state_to_float(state_getter(override_entity_id))
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
        return state_to_float(state)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _room_debug_attributes(room: RoomProfile, recommendation: RoomRecommendation) -> dict[str, Any]:
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
