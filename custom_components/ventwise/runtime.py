"""Runtime models and helpers for the integration layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Callable, Mapping

from ventwise_core import (
    ComfortObservation,
    RecommendationSummary,
    RoomObservation,
    RoomProfile,
    ScoringConfig,
)

from .const import (
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_MASTER_CONTROL_ENTITY_ID,
    CONF_MINIMUM_SCORE,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WEIGHT,
    CONF_ROOMS,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_TEMPERATURE_C,
    CONF_WIND_SPEED_ENTITY_ID,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_ROOM_WEIGHT,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_STABILITY_MINUTES,
    DEFAULT_TARGET_TEMPERATURE_C,
)
from ventwise_core import ComfortRecommender


@dataclass(frozen=True, slots=True)
class RoomConfig:
    """Serializable room configuration stored in the config entry."""

    name: str
    temperature_entity_id: str
    humidity_entity_id: str
    weight: float = DEFAULT_ROOM_WEIGHT


@dataclass(frozen=True, slots=True)
class IntegrationConfig:
    """Normalised configuration for the integration runtime."""

    target_temperature_c: float = DEFAULT_TARGET_TEMPERATURE_C
    soft_outdoor_threshold_c: float = DEFAULT_SOFT_OUTDOOR_THRESHOLD_C
    minimum_score: float = DEFAULT_MINIMUM_SCORE
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
    stability_minutes: int = DEFAULT_STABILITY_MINUTES
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = DEFAULT_QUIET_HOURS_START
    quiet_hours_end: str = DEFAULT_QUIET_HOURS_END
    enabled: bool = True
    outdoor_temperature_entity_id: str = ""
    outdoor_humidity_entity_id: str = ""
    wind_speed_entity_id: str | None = None
    master_control_entity_id: str | None = None
    notification_device_id: str | None = None
    rooms: tuple[RoomConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Result of a coordinator refresh."""

    summary: RecommendationSummary
    notification_allowed: bool
    quiet_hours_active: bool
    cooldown_active: bool
    enabled: bool
    stable_for_seconds: int
    last_updated: datetime


def build_integration_config(data: Mapping[str, Any]) -> IntegrationConfig:
    """Convert raw config entry data into a runtime config object."""

    rooms = tuple(
        RoomConfig(
            name=str(room[CONF_ROOM_NAME]),
            temperature_entity_id=str(room[CONF_ROOM_TEMPERATURE_ENTITY_ID]),
            humidity_entity_id=str(room[CONF_ROOM_HUMIDITY_ENTITY_ID]),
            weight=float(room.get(CONF_ROOM_WEIGHT, DEFAULT_ROOM_WEIGHT)),
        )
        for room in data.get(CONF_ROOMS, [])
    )
    return IntegrationConfig(
        target_temperature_c=float(data.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C)),
        soft_outdoor_threshold_c=float(
            data.get(CONF_SOFT_OUTDOOR_THRESHOLD_C, DEFAULT_SOFT_OUTDOOR_THRESHOLD_C)
        ),
        minimum_score=float(data.get(CONF_MINIMUM_SCORE, DEFAULT_MINIMUM_SCORE)),
        cooldown_minutes=int(data.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES)),
        stability_minutes=int(data.get(CONF_STABILITY_MINUTES, DEFAULT_STABILITY_MINUTES)),
        quiet_hours_enabled=bool(data.get(CONF_QUIET_HOURS_ENABLED, True)),
        quiet_hours_start=str(data.get(CONF_QUIET_HOURS_START, DEFAULT_QUIET_HOURS_START)),
        quiet_hours_end=str(data.get(CONF_QUIET_HOURS_END, DEFAULT_QUIET_HOURS_END)),
        enabled=bool(data.get(CONF_ENABLED, True)),
        outdoor_temperature_entity_id=str(data.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID, "")),
        outdoor_humidity_entity_id=str(data.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID, "")),
        wind_speed_entity_id=_string_or_none(data.get(CONF_WIND_SPEED_ENTITY_ID)),
        master_control_entity_id=_string_or_none(data.get(CONF_MASTER_CONTROL_ENTITY_ID)),
        notification_device_id=_string_or_none(data.get(CONF_NOTIFICATION_DEVICE_ID)),
        rooms=rooms,
    )


def build_scoring_config(config: IntegrationConfig) -> ScoringConfig:
    """Translate integration config into core scoring config."""

    return ScoringConfig(
        target_temperature_c=config.target_temperature_c,
        soft_outdoor_threshold_c=config.soft_outdoor_threshold_c,
        minimum_score=config.minimum_score,
        minimum_stability_seconds=config.stability_minutes * 60,
    )


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

    outdoor_temp = state_to_float(state_getter(config.outdoor_temperature_entity_id))
    outdoor_humidity = state_to_float(state_getter(config.outdoor_humidity_entity_id))
    if outdoor_temp is None or outdoor_humidity is None:
        outdoor = None
    else:
        wind_speed = state_to_float(state_getter(config.wind_speed_entity_id)) if config.wind_speed_entity_id else None
        outdoor = ComfortObservation(
            temperature_c=outdoor_temp,
            humidity_percent=outdoor_humidity,
            wind_speed_m_s=wind_speed,
        )

    rooms: list[RoomProfile] = []
    for room in config.rooms:
        temperature = state_to_float(state_getter(room.temperature_entity_id))
        humidity = state_to_float(state_getter(room.humidity_entity_id))
        if temperature is None or humidity is None:
            continue
        rooms.append(
            RoomProfile(
                name=room.name,
                indoor=RoomObservation(
                    temperature_c=temperature,
                    humidity_percent=humidity,
                ),
                weight=room.weight,
            )
        )

    return rooms, outdoor


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_time(value: str) -> time:
    text = value.strip()
    if len(text.split(":")) == 2:
        return datetime.strptime(text, "%H:%M").time()
    return datetime.strptime(text, "%H:%M:%S").time()
