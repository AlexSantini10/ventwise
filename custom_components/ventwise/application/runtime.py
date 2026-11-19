"""Runtime models and helpers for the integration layer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Callable, Mapping
from datetime import datetime, time
from typing import Any

from ..ventwise_core import (
    AggregateDecisionResult,
    Availability,
    ComfortObservation,
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    ExternalConditions,
    DecisionRoom,
    DecisionSnapshot,
    ForecastObservation,
    Observation,
    RecommendationAction,
    RecommendationSummary,
    RoomObservation,
    RoomGuardrailState,
    RoomProfile,
    SourceReading,
    RoomRecommendation,
    TraceEntry,
)
from ..ventwise_core.serialization import (
    aggregate_result_to_dict,
    result_to_dict,
    snapshot_to_dict,
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
    CONF_SAFETY_BYPASS_QUIET_HOURS,
    CONF_ROOM_KIND,
    CONF_ROOM_ENABLED,
    CONF_ROOM_ID,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_CO2_ENABLED,
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
    DEFAULT_SAFETY_BYPASS_QUIET_HOURS,
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
from ..units import (
    normalize_measurement, state_unit, temperature_to_celsius, temperature_unit,
    wind_speed_to_m_s, wind_speed_unit,
)


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
    co2_enabled: bool = False
    co2_entity_id: str | None = None
    window_sensor_entity_ids: tuple[str, ...] = ()
    start_entity_id: str | None = None
    stop_entity_id: str | None = None
    action_change_hold_minutes: int = DEFAULT_ROOM_ACTION_CHANGE_HOLD_MINUTES
    action_lockout_minutes: int = DEFAULT_ROOM_ACTION_LOCKOUT_MINUTES


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
    safety_bypass_quiet_hours: bool = DEFAULT_SAFETY_BYPASS_QUIET_HOURS
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
    outdoor_pressure_hpa: float | None = None
    window_states: Mapping[str, str] = field(default_factory=dict)
    core_snapshot: DecisionSnapshot | None = None
    core_result: AggregateDecisionResult | None = None
    calculated_result: AggregateDecisionResult | None = None
    delivered_result: AggregateDecisionResult | None = None


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

    legacy_co2_enabled = bool(data.get(CONF_CO2_ENABLED, False))
    legacy_co2_entity_id = _string_or_none(data.get(CONF_CO2_ENTITY_ID))
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
            co2_enabled=bool(
                room.get(
                    CONF_ROOM_CO2_ENABLED,
                    legacy_co2_enabled
                    and bool(
                        _string_or_none(room.get(CONF_ROOM_CO2_ENTITY_ID))
                        or legacy_co2_entity_id
                    ),
                )
            ),
            co2_entity_id=(
                _string_or_none(room.get(CONF_ROOM_CO2_ENTITY_ID))
                or (legacy_co2_entity_id if legacy_co2_enabled else None)
            ),
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
        safety_bypass_quiet_hours=bool(
            data.get(CONF_SAFETY_BYPASS_QUIET_HOURS, DEFAULT_SAFETY_BYPASS_QUIET_HOURS)
        ),
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
        co2_enabled=any(room.co2_enabled for room in rooms),
        co2_entity_id=legacy_co2_entity_id,
        co2_threshold_ppm=float(data.get(CONF_CO2_THRESHOLD_PPM, DEFAULT_CO2_THRESHOLD_PPM)),
        notification_device_ids=_string_list(data.get(CONF_NOTIFICATION_DEVICE_ID)),
        rooms=rooms,
    )


def build_decision_config(config: IntegrationConfig) -> DecisionConfig:
    """Translate integration settings into the active DDP configuration."""

    return DecisionConfig(
        target_temperature_c=config.target_temperature_c,
        meaningful_benefit=max(0.0, config.minimum_score),
        co2_enabled=config.co2_enabled,
        co2_threshold_ppm=config.co2_threshold_ppm,
    )


def build_decision_snapshot(
    rooms: list[RoomProfile],
    outdoor: ComfortObservation,
    evaluated_at: datetime,
    *,
    window_states: Mapping[str, str] | None = None,
    room_action_guards: Mapping[str, "RoomActionGuard"] | None = None,
) -> DecisionSnapshot:
    """Build the immutable core input from already normalized HA values."""

    source_times = [
        reading.observed_at
        for reading in (
            *(room.indoor.temperature_source for room in rooms),
            *(room.indoor.humidity_source for room in rooms),
            *(room.co2_source for room in rooms),
            outdoor.temperature_source,
            outdoor.humidity_source,
            outdoor.wind_speed_source,
            outdoor.wind_gust_source,
            outdoor.pressure_source,
        )
        if reading is not None and reading.observed_at is not None
    ]
    snapshot_evaluated_at = max((evaluated_at, *source_times))

    def observation(value: Any, unit: str, source_id: str, measurement: str, source: SourceReading | None = None) -> Observation:
        reading = source or SourceReading(value, unit, snapshot_evaluated_at, f"manual:{source_id}")
        normalized, canonical, reason = normalize_measurement(reading.value, reading.unit or unit, measurement)
        expected_classes = {
            "temperature": {"temperature"}, "humidity": {"humidity"}, "wind_speed": {"wind_speed"}, "co2": {"carbon_dioxide", "co2"},
        }
        if reading.device_class and reading.device_class not in expected_classes.get(measurement, {reading.device_class}):
            reason = "contradictory_device_class"
            normalized = None
        if reason is None and normalized is not None:
            limits = {"temperature": (-90.0, 70.0), "humidity": (0.0, 100.0), "wind_speed": (0.0, 150.0), "co2": (0.0, 100000.0)}
            lower, upper = limits.get(measurement, (-float("inf"), float("inf")))
            if not lower <= normalized <= upper:
                reason = "out_of_range"
                normalized = None
        # Older test doubles and legacy adapters may not expose HA's timestamp;
        # preserve their established refresh-time semantics while real HA
        # states retain last_updated above.
        observed_at = reading.observed_at or snapshot_evaluated_at
        availability = Availability.AVAILABLE if reason is None and normalized is not None else (
            Availability.MISSING if reason == "missing" else Availability.INVALID
        )
        return Observation(
            normalized, canonical, observed_at, reading.source_id,
            availability=availability, quality_reason=reason,
            original_value=reading.value, original_unit=reading.unit,
        )

    window_states = window_states or {}
    decision_rooms = tuple(
        DecisionRoom(
            room_id=room.room_id or room.name,
            name=room.name,
            temperature_c=observation(room.indoor.temperature_c, "°C", room.room_id or room.name, "temperature", room.indoor.temperature_source),
            humidity_percent=observation(room.indoor.humidity_percent, "%", room.room_id or room.name, "humidity", room.indoor.humidity_source),
            window_open=(
                Observation(window_states[room.room_id or room.name] == WINDOW_STATE_OPEN, "", snapshot_evaluated_at, f"manual:{room.room_id or room.name}")
                if (room.room_id or room.name) in window_states
                and window_states[room.room_id or room.name] in {WINDOW_STATE_OPEN, WINDOW_STATE_CLOSED}
                else None
            ),
            window_contact_configured=(room.room_id or room.name) in window_states
            and window_states[room.room_id or room.name] != WINDOW_STATE_NOT_CONFIGURED,
            action_change_hold_seconds=getattr(room, "action_change_hold_minutes", 0) * 60,
            action_lockout_seconds=getattr(room, "action_lockout_minutes", 0) * 60,
            target_temperature_c=(
                room.target_temperature_c_override
                if room.target_temperature_c_override_enabled
                else None
            ),
            target_humidity_percent=(
                room.target_humidity_percent_override
                if room.target_humidity_percent_override_enabled
                else None
            ),
            co2_ppm=observation(room.co2_ppm, "ppm", room.room_id or room.name, "co2", room.co2_source)
            if room.co2_ppm is not None or room.co2_source is not None else None,
        )
        for room in rooms
        if room.enabled
    )
    return DecisionSnapshot(
        rooms=decision_rooms,
        outdoor=ExternalConditions(
            temperature_c=observation(outdoor.temperature_c, "°C", "outdoor", "temperature", outdoor.temperature_source),
            humidity_percent=observation(outdoor.humidity_percent, "%", "outdoor", "humidity", outdoor.humidity_source),
            wind_speed_m_s=(observation(outdoor.wind_speed_m_s, "m/s", "outdoor", "wind_speed", outdoor.wind_speed_source) if outdoor.wind_speed_m_s is not None else None),
            wind_gust_m_s=(observation(outdoor.wind_gust_m_s, "m/s", "outdoor", "wind_speed", outdoor.wind_gust_source) if outdoor.wind_gust_m_s is not None else None),
            pressure_hpa=(observation(outdoor.pressure_hpa, "hPa", "outdoor", "pressure", outdoor.pressure_source) if outdoor.pressure_hpa is not None else None),
            weather_condition=(Observation(outdoor.weather_condition, "", snapshot_evaluated_at, "manual:outdoor") if outdoor.weather_condition is not None else None),
            forecast=outdoor.forecast,
            safety_evidence_configured=outdoor.safety_evidence_configured,
        ),
        evaluated_at=snapshot_evaluated_at,
        context=DecisionContext(
            stable_for_seconds=10**9,
            room_guardrails=tuple(
                RoomGuardrailState(
                    room_id=room_id,
                    accepted_action=guard.accepted_action,
                    lockout_until=guard.lockout_until,
                    pending_action=guard.pending_action,
                    pending_since=guard.pending_since,
                )
                for room_id, guard in sorted((room_action_guards or {}).items())
            ),
        ),
    )


def decision_to_summary(
    engine: DecisionEngine,
    snapshot: DecisionSnapshot,
    result: AggregateDecisionResult | None = None,
) -> RecommendationSummary:
    """Render a pure DDP result for existing HA presentation entities."""

    result = result or engine.evaluate(snapshot)
    recommendations = tuple(
        RoomRecommendation(
            room_id=room.room_id,
            room_name=room.name,
            action=room_result.core_action,
            score=room_result.score,
            reason=room_result.reason,
            target_perceived_c=room_result.target_perceived_c,
            indoor_perceived_c=room_result.indoor_perceived_c,
            outdoor_perceived_c=room_result.outdoor_perceived_c,
            suggested_comfort_temperature_c=room_result.suggested_comfort_temperature_c,
            open_score=room_result.candidate_scores.open,
            close_score=room_result.candidate_scores.close,
            reason_code=room_result.reason_code,
            ventilation_duration_minutes=(10 if room_result.core_action is RecommendationAction.VENTILATE else None),
            indoor_comfort_severity=abs(room_result.indoor_perceived_c - room_result.target_perceived_c),
            outdoor_comfort_severity=abs(room_result.outdoor_perceived_c - room_result.target_perceived_c),
            co2_ppm=room_result.co2_ppm,
            co2_influence=room_result.co2_influence,
        )
        for room_result in result.room_results
        for room in snapshot.rooms
        if room.room_id == room_result.room_id
    )
    selected_room_id = result.trace[0].detail if result.trace else None
    selected = next(
        (
            item
            for item in recommendations
            if item.room_id == selected_room_id
            and item.action is not RecommendationAction.NONE
        ),
        None,
    )
    blocked_by = None
    if (
        selected is None
        and recommendations
        and all(item.action is RecommendationAction.NONE for item in recommendations)
        and any(
            item.reason_code in {"window_already_open", "window_already_closed"}
            for item in recommendations
        )
    ):
        blocked_by = "window_state"
    return RecommendationSummary(
        action=result.core_action,
        score=selected.score if selected else 0.0,
        reason=selected.reason if selected else "No actionable recommendation.",
        suggested_comfort_temperature_c=(selected.suggested_comfort_temperature_c if selected else None),
        room_recommendations=recommendations,
        blocked_by=blocked_by,
        best_room=selected.room_name if selected else None,
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

    outdoor_temp_state = _outdoor_state(
        config.outdoor_temperature_source,
        config.outdoor_weather_entity_id,
        config.outdoor_temperature_entity_id,
        state_getter,
        "temperature",
    )
    outdoor_temp = _canonical_measurement_value(
        state_to_float(outdoor_temp_state), outdoor_temp_state, "temperature"
    )
    outdoor_humidity_state = _outdoor_state(
        config.outdoor_humidity_source,
        config.outdoor_weather_entity_id,
        config.outdoor_humidity_entity_id,
        state_getter,
        "humidity",
    )
    outdoor_humidity = state_to_float(outdoor_humidity_state)
    if outdoor_temp is None:
        outdoor = None
    else:
        weather_condition = _weather_condition(
            config.outdoor_weather_entity_id,
            state_getter,
        )
        wind_speed_state = _outdoor_state(
            config.wind_speed_source,
            config.outdoor_weather_entity_id,
            config.wind_speed_entity_id,
            state_getter,
            "wind_speed",
        )
        wind_speed = _canonical_measurement_value(state_to_float(wind_speed_state), wind_speed_state, "wind_speed")
        wind_gust = _weather_gust_value(
            config.outdoor_weather_entity_id,
            state_getter,
        )
        pressure_state = _weather_pressure_state(
            config.outdoor_weather_entity_id,
            state_getter,
        )
        pressure_hpa = _canonical_measurement_value(
            state_to_float(pressure_state), pressure_state, "pressure"
        )
        outdoor = ComfortObservation(
            temperature_c=outdoor_temp,
            humidity_percent=outdoor_humidity,
            wind_speed_m_s=wind_speed,
            wind_gust_m_s=wind_gust,
            pressure_hpa=pressure_hpa,
            weather_condition=weather_condition,
            forecast_temperature_c=forecast_temperature_c,
            forecast=forecast,
            temperature_source=_source_reading(outdoor_temp_state, "temperature", "outdoor.temperature"),
            humidity_source=_source_reading(outdoor_humidity_state, "humidity", "outdoor.humidity"),
            wind_speed_source=_source_reading(wind_speed_state, "wind_speed", "outdoor.wind") if wind_speed_state is not None else None,
            wind_gust_source=_source_reading(
                _outdoor_state(
                    config.wind_speed_source,
                    config.outdoor_weather_entity_id,
                    config.wind_speed_entity_id,
                    state_getter,
                    "wind_gust",
                ),
                "wind_speed",
                "outdoor.gust",
            ),
            pressure_source=_source_reading(
                pressure_state,
                "pressure",
                "outdoor.pressure",
            ) if pressure_state is not None else None,
            safety_evidence_configured=bool(
                config.outdoor_weather_entity_id
                or config.wind_speed_entity_id
            ),
        )

    rooms: list[RoomProfile] = []
    for room in config.rooms:
        temperature_state = state_getter(room.temperature_entity_id)
        humidity_state = state_getter(room.humidity_entity_id) if room.humidity_entity_id else None
        temperature = state_to_temperature_c(temperature_state)
        humidity = state_to_float(humidity_state) if humidity_state is not None else None
        co2, co2_source = room_co2_reading(room, state_getter)
        if temperature is None:
            continue
        rooms.append(
            RoomProfile(
                room_id=room.room_id,
                name=room.name,
                indoor=RoomObservation(
                    temperature_c=temperature,
                    humidity_percent=humidity,
                    temperature_source=_source_reading(temperature_state, "temperature", room.temperature_entity_id),
                    humidity_source=_source_reading(humidity_state, "humidity", room.humidity_entity_id) if humidity_state is not None else None,
                ),
                kind=room.kind,
                enabled=room.enabled,
                target_temperature_c_override_enabled=room.target_temperature_c_override_enabled,
                target_temperature_c_override=room.target_temperature_c_override,
                target_humidity_percent_override_enabled=room.target_humidity_percent_override_enabled,
                target_humidity_percent_override=room.target_humidity_percent_override,
                co2_ppm=co2,
                co2_source=co2_source,
            )
        )

    return rooms, outdoor


def room_co2_reading(
    room: RoomConfig,
    state_getter: Callable[[str], Any],
) -> tuple[float | None, SourceReading | None]:
    """Return the effective, per-room CO₂ value and its source metadata."""

    if not room.co2_enabled or not room.co2_entity_id:
        return None, None
    state = state_getter(room.co2_entity_id)
    value = state_to_float(state)
    source = _source_reading(state, "co2", room.co2_entity_id)
    if source is None:
        source = SourceReading(None, "ppm", None, room.co2_entity_id)
    return value, source


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
        "outdoor_pressure_hpa": snapshot.outdoor_pressure_hpa,
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
        "safety_bypass_quiet_hours": config.safety_bypass_quiet_hours,
        "room_recommendations": room_details,
        "best_room_recommendation": best_room_details,
        "normalized_input_snapshot": (
            snapshot_to_dict(snapshot.core_snapshot)
            if snapshot.core_snapshot is not None
            else None
        ),
        "core_result": (
            aggregate_result_to_dict(snapshot.core_result)
            if snapshot.core_result is not None
            else None
        ),
        "calculated_result": (
            aggregate_result_to_dict(snapshot.calculated_result)
            if snapshot.calculated_result is not None
            else None
        ),
        "delivered_result": (
            aggregate_result_to_dict(snapshot.delivered_result)
            if snapshot.delivered_result is not None
            else None
        ),
        "decision_context": (
            snapshot_to_dict(snapshot.core_snapshot).get("context")
            if snapshot.core_snapshot is not None
            else None
        ),
        "delivery_transformations": _delivery_transformations(
            snapshot.core_result,
            snapshot.delivered_result,
        ),
    }


def build_delivered_result(
    core_result: AggregateDecisionResult,
    _summary: RecommendationSummary,
    suppressed_by: Mapping[str, str] | None = None,
) -> AggregateDecisionResult:
    """Project HA delivery filters onto the pure core result."""

    suppressed_by = suppressed_by or {}
    room_results = tuple(
        replace(
            result,
            delivered_action=(
                RecommendationAction.NONE
                if result.room_id in suppressed_by
                else result.core_action
            ),
            delivery_suppressed_by=(
                suppressed_by.get(result.room_id)
                if result.room_id in suppressed_by
                else None
            ),
        )
        for result in core_result.room_results
    )
    delivered_candidates = [
        item for item in room_results if item.delivered_action is not RecommendationAction.NONE
    ]
    selected = max(
        delivered_candidates,
        key=lambda item: (item.score, item.room_id),
        default=None,
    )
    return replace(
        core_result,
        # The core action is immutable truth; only delivery eligibility changes.
        core_action=core_result.core_action,
        delivered_action=selected.delivered_action if selected else RecommendationAction.NONE,
        room_results=room_results,
        trace=core_result.trace + (TraceEntry("delivery.projected"),),
    )


def build_room_diagnostic_attributes(
    snapshot: RuntimeSnapshot,
    room_id: str,
) -> dict[str, Any]:
    """Return the complete structured core/delivery view for one room."""

    core = next(
        (item for item in (snapshot.core_result.room_results if snapshot.core_result else ())
         if item.room_id == room_id),
        None,
    )
    calculated = next(
        (item for item in (snapshot.calculated_result.room_results if snapshot.calculated_result else ())
         if item.room_id == room_id),
        None,
    )
    delivered = next(
        (item for item in (snapshot.delivered_result.room_results if snapshot.delivered_result else ())
         if item.room_id == room_id),
        None,
    )
    normalized = snapshot_to_dict(snapshot.core_snapshot) if snapshot.core_snapshot else None
    room_input = None
    if normalized is not None:
        room_input = next(
            (item for item in normalized["rooms"] if item["room_id"] == room_id),
            None,
        )
    return {
        "normalized_input": {
            "room": room_input,
            "outdoor": normalized["outdoor"] if normalized else None,
            "evaluated_at": normalized["evaluated_at"] if normalized else None,
        },
        "core_result": result_to_dict(core) if core else None,
        "calculated_result": result_to_dict(calculated) if calculated else None,
        "delivered_result": result_to_dict(delivered) if delivered else None,
        "aggregate_core_result": (
            aggregate_result_to_dict(snapshot.core_result)
            if snapshot.core_result
            else None
        ),
        "aggregate_delivered_result": (
            aggregate_result_to_dict(snapshot.delivered_result)
            if snapshot.delivered_result
            else None
        ),
        "core_action": core.core_action.value if core else RecommendationAction.NONE.value,
        "calculated_action": calculated.core_action.value if calculated else RecommendationAction.NONE.value,
        "delivered_action": delivered.delivered_action.value if delivered else RecommendationAction.NONE.value,
        "delivery_suppressed_by": delivered.delivery_suppressed_by if delivered else None,
    }


def _delivery_transformations(
    core_result: AggregateDecisionResult | None,
    delivered_result: AggregateDecisionResult | None,
) -> list[dict[str, Any]]:
    if core_result is None or delivered_result is None:
        return []
    delivered_by_room = {item.room_id: item for item in delivered_result.room_results}
    return [
        {
            "room_id": item.room_id,
            "core_action": item.core_action.value,
            "delivered_action": delivered_by_room.get(item.room_id, item).delivered_action.value,
            "suppressed_by": delivered_by_room.get(item.room_id, item).delivery_suppressed_by,
        }
        for item in core_result.room_results
    ]


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
    if measurement == "pressure":
        unit = state_unit(state, "hPa", "pressure")
        factors = {"hPa": 1.0, "Pa": 0.01, "kPa": 10.0, "bar": 1000.0, "atm": 1013.25, "psi": 68.9475729, "inHg": 33.8638867}
        return value * factors.get(unit, 1.0)
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


def _weather_pressure_state(
    weather_entity_id: str | None,
    state_getter: Callable[[str], Any],
) -> Any | None:
    """Return atmospheric pressure from the configured weather entity."""

    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    for key in ("pressure", "pressure_hpa", "atmospheric_pressure"):
        value = attributes.get(key)
        if value is not None:
            return type(
                "AttributeState",
                (),
                {
                    "state": value,
                    "attributes": attributes,
                    "last_updated": getattr(state, "last_updated", None),
                },
            )()
    return None


def _outdoor_state(
    source: str,
    weather_entity_id: str | None,
    override_entity_id: str | None,
    state_getter: Callable[[str], Any],
    attribute_name: str,
) -> Any | None:
    """Select one configured source deterministically and retain its HA state."""
    if source == OUTDOOR_SOURCE_OVERRIDE and override_entity_id:
        return state_getter(override_entity_id)
    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    if attribute_name in attributes:
        return type("AttributeState", (), {
            "state": attributes[attribute_name],
            "attributes": attributes,
            "last_updated": getattr(state, "last_updated", None),
        })()
    return state if attribute_name == "temperature" else None


def _source_reading(state: Any | None, measurement: str, source_id: str | None) -> SourceReading | None:
    if state is None:
        return None
    attributes = getattr(state, "attributes", {}) or {}
    fallback_units = {"temperature": "°C", "humidity": "%", "wind_speed": "m/s", "pressure": "hPa", "co2": "ppm"}
    unit = state_unit(state, fallback_units.get(measurement, ""), measurement)
    observed_at = getattr(state, "last_updated", None) or getattr(state, "last_changed", None)
    return SourceReading(
        getattr(state, "state", None), unit, observed_at, source_id,
        attributes.get("device_class"),
    )


def find_room_recommendation(
    summary: RecommendationSummary,
    room: RoomConfig,
) -> Any | None:
    """Find the recommendation matching a room config."""

    room_key = room.room_id or room.name
    for recommendation in summary.room_recommendations:
        if recommendation.room_id == room_key:
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
