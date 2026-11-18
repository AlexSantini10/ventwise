"""Stable JSON serialization for standalone VentWise evaluation."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Mapping

from .decision import DecisionConfig, DecisionEngine
from .models import (
    AggregateDecisionResult,
    Availability,
    CandidateScores,
    DataQualitySummary,
    DecisionContext,
    DecisionOutdoor,
    DecisionResult,
    DecisionRoom,
    DecisionSnapshot,
    ForecastObservation,
    Observation,
    RoomGuardrailState,
    RecommendationAction,
    TraceEntry,
    Validity,
)

SCHEMA_VERSION = "ventwise.engine.v3"


def _datetime(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _enum(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def observation_to_dict(observation: Observation[Any] | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "value": observation.value,
        "unit": observation.unit,
        "original_value": observation.original_value,
        "original_unit": observation.original_unit,
        "observed_at": _datetime(observation.observed_at),
        "source_id": observation.source_id,
        "validity": observation.validity.value,
        "availability": observation.availability.value,
        "freshness_seconds": (
            observation.freshness.total_seconds()
            if observation.freshness is not None
            else None
        ),
        "quality_reason": observation.quality_reason,
        "provenance": list(observation.provenance),
    }


def snapshot_to_dict(snapshot: DecisionSnapshot) -> dict[str, Any]:
    def room_to_dict(room: DecisionRoom) -> dict[str, Any]:
        return {
            "room_id": room.room_id,
            "name": room.name,
            "temperature_c": observation_to_dict(room.temperature_c),
            "humidity_percent": observation_to_dict(room.humidity_percent),
            "window_open": observation_to_dict(room.window_open),
            "target_temperature_c": room.target_temperature_c,
            "target_humidity_percent": room.target_humidity_percent,
            "co2_ppm": observation_to_dict(room.co2_ppm),
            "window_contact_configured": room.window_contact_configured,
            "action_change_hold_seconds": room.action_change_hold_seconds,
            "action_lockout_seconds": room.action_lockout_seconds,
        }

    outdoor = snapshot.outdoor
    return {
        "rooms": [room_to_dict(room) for room in snapshot.rooms],
        "outdoor": {
            "temperature_c": observation_to_dict(outdoor.temperature_c),
            "humidity_percent": observation_to_dict(outdoor.humidity_percent),
            "wind_speed_m_s": observation_to_dict(outdoor.wind_speed_m_s),
            "wind_gust_m_s": observation_to_dict(outdoor.wind_gust_m_s),
            "weather_condition": observation_to_dict(outdoor.weather_condition),
        "forecast": _json_value(outdoor.forecast),
            "safety_evidence_configured": outdoor.safety_evidence_configured,
            "pressure_hpa": observation_to_dict(outdoor.pressure_hpa),
        },
        "evaluated_at": snapshot.evaluated_at.isoformat(),
        "context": _json_value(snapshot.context),
    }


def result_to_dict(result: DecisionResult) -> dict[str, Any]:
    return _json_value(result)


def aggregate_result_to_dict(result: AggregateDecisionResult) -> dict[str, Any]:
    return _json_value(result)


def config_to_dict(config: DecisionConfig) -> dict[str, Any]:
    return _json_value(config)


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 string") from exc


def _observation(value: Any, field: str) -> Observation[Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object or null")
    observed_at = value.get("observed_at")
    freshness = value.get("freshness_seconds")
    try:
        validity = Validity(value.get("validity", Validity.VALID.value))
        availability = Availability(value.get("availability", Availability.AVAILABLE.value))
    except ValueError as exc:
        raise ValueError(f"{field} has an unsupported quality value") from exc
    return Observation(
        value=value.get("value"),
        unit=str(value.get("unit", "")),
        observed_at=_parse_datetime(observed_at, f"{field}.observed_at") if observed_at else None,
        source_id=value.get("source_id"),
        validity=validity,
        availability=availability,
        freshness=timedelta(seconds=float(freshness)) if freshness is not None else None,
        quality_reason=value.get("quality_reason"),
        provenance=tuple(str(item) for item in value.get("provenance", ())),
        original_value=value.get("original_value", value.get("value")),
        original_unit=value.get("original_unit", value.get("unit", "")),
    )


def snapshot_from_dict(data: Mapping[str, Any]) -> DecisionSnapshot:
    if not isinstance(data, Mapping):
        raise ValueError("scenario must be a JSON object")
    rooms = tuple(
        DecisionRoom(
            room_id=str(room["room_id"]),
            name=str(room.get("name", room["room_id"])),
            temperature_c=_observation(room["temperature_c"], f"rooms[{index}].temperature_c"),
            humidity_percent=_observation(room.get("humidity_percent"), f"rooms[{index}].humidity_percent"),
            window_open=_observation(room.get("window_open"), f"rooms[{index}].window_open"),
            target_temperature_c=room.get("target_temperature_c"),
            target_humidity_percent=room.get("target_humidity_percent"),
            co2_ppm=_observation(room.get("co2_ppm"), f"rooms[{index}].co2_ppm"),
            window_contact_configured=bool(room.get("window_contact_configured", False)),
            action_change_hold_seconds=int(room.get("action_change_hold_seconds", 0)),
            action_lockout_seconds=int(room.get("action_lockout_seconds", 0)),
        )
        for index, room in enumerate(data.get("rooms", ()))
    )
    raw_outdoor = data["outdoor"]
    raw_forecast = raw_outdoor.get("forecast")
    forecast = (
        ForecastObservation(
            temperature_c=raw_forecast.get("temperature_c"),
            humidity_percent=raw_forecast.get("humidity_percent"),
            wind_speed_m_s=raw_forecast.get("wind_speed_m_s"),
            wind_gust_m_s=raw_forecast.get("wind_gust_m_s"),
            weather_condition=raw_forecast.get("weather_condition"),
            precipitation_probability=raw_forecast.get("precipitation_probability"),
        )
        if isinstance(raw_forecast, Mapping)
        else None
    )
    outdoor = DecisionOutdoor(
        temperature_c=_observation(raw_outdoor["temperature_c"], "outdoor.temperature_c"),
        humidity_percent=_observation(raw_outdoor.get("humidity_percent"), "outdoor.humidity_percent"),
        wind_speed_m_s=_observation(raw_outdoor.get("wind_speed_m_s"), "outdoor.wind_speed_m_s"),
        wind_gust_m_s=_observation(raw_outdoor.get("wind_gust_m_s"), "outdoor.wind_gust_m_s"),
        weather_condition=_observation(raw_outdoor.get("weather_condition"), "outdoor.weather_condition"),
        forecast=forecast,
        safety_evidence_configured=bool(raw_outdoor.get("safety_evidence_configured", False)),
        pressure_hpa=_observation(raw_outdoor.get("pressure_hpa"), "outdoor.pressure_hpa"),
    )
    raw_context = data.get("context", {})
    raw_guardrails = raw_context.get("room_guardrails", ())
    guardrails = tuple(
        RoomGuardrailState(
            room_id=str(item["room_id"]),
            accepted_action=item.get("accepted_action"),
            lockout_until=_parse_datetime(item["lockout_until"], "context.room_guardrails.lockout_until") if item.get("lockout_until") else None,
            pending_action=item.get("pending_action"),
            pending_since=_parse_datetime(item["pending_since"], "context.room_guardrails.pending_since") if item.get("pending_since") else None,
        )
        for item in raw_guardrails
    )
    context = DecisionContext(
        quiet_hours_active=bool(raw_context.get("quiet_hours_active", False)),
        cooldown_active=bool(raw_context.get("cooldown_active", False)),
        stable_for_seconds=int(raw_context.get("stable_for_seconds", 0)),
        stability_seconds_required=int(raw_context.get("stability_seconds_required", 0)),
        room_guardrails=guardrails,
    )
    return DecisionSnapshot(
        rooms=rooms,
        outdoor=outdoor,
        evaluated_at=_parse_datetime(data["evaluated_at"], "evaluated_at"),
        context=context,
    )


def evaluate_scenario(data: Mapping[str, Any]) -> dict[str, Any]:
    config = DecisionConfig(**dict(data.get("config", {})))
    snapshot = snapshot_from_dict(data)
    result = DecisionEngine(config).evaluate(snapshot)
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_at": snapshot.evaluated_at.isoformat(),
        "config": config_to_dict(config),
        "normalized_input": snapshot_to_dict(snapshot),
        "core_result": aggregate_result_to_dict(result),
    }
