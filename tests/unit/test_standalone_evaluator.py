"""Tests for the dependency-free VentWise evaluator contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from ventwise_core import (
    DecisionContext,
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    RecommendationSummary,
    RoomRecommendation,
)
from custom_components.ventwise.application.runtime import build_delivered_result
from ventwise_core.serialization import (
    evaluate_scenario,
    snapshot_from_dict,
    snapshot_to_dict,
)


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _observation(value, unit, source):
    return {
        "value": value,
        "unit": unit,
        "observed_at": NOW.isoformat(),
        "source_id": source,
    }


def scenario(*, indoor=28.0, outdoor=20.0, weather="clear", context=None):
    return {
        "evaluated_at": NOW.isoformat(),
        "config": {"co2_enabled": True},
        "context": context or {},
        "rooms": [
            {
                "room_id": "bedroom",
                "name": "Bedroom",
                "temperature_c": _observation(indoor, "°C", "sensor.bedroom_temperature"),
                "humidity_percent": _observation(50.0, "%", "sensor.bedroom_humidity"),
                "co2_ppm": _observation(1800.0, "ppm", "sensor.bedroom_co2"),
                "window_open": _observation(False, "", "binary_sensor.bedroom_window"),
                "window_contact_configured": True,
            }
        ],
        "outdoor": {
            "temperature_c": _observation(outdoor, "°C", "weather.home"),
            "humidity_percent": _observation(50.0, "%", "weather.home"),
            "wind_speed_m_s": _observation(1.0, "m/s", "weather.home"),
            "weather_condition": _observation(weather, "", "weather.home"),
            "safety_evidence_configured": True,
        },
    }


def test_evaluator_output_is_json_stable_and_complete():
    first = evaluate_scenario(scenario())
    second = evaluate_scenario(scenario())

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )
    assert first["schema_version"] == "ventwise.engine.v2"
    assert first["normalized_input"]["rooms"][0]["temperature_c"]["source_id"] == (
        "sensor.bedroom_temperature"
    )
    result = first["core_result"]["room_results"][0]
    assert result["core_action"] in {"open", "ventilate", "close", "none"}
    assert set(result["candidate_scores"]) >= {"open", "ventilate", "close", "none"}
    assert result["trace"]
    assert result["data_quality"]["used"]


def test_snapshot_serialization_round_trip_preserves_engine_input():
    snapshot = snapshot_from_dict(scenario())
    assert snapshot_from_dict(snapshot_to_dict(snapshot)) == snapshot


def test_cli_emits_only_deterministic_json():
    completed = subprocess.run(
        [sys.executable, "-m", "ventwise_core"],
        input=json.dumps(scenario()),
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )
    parsed = json.loads(completed.stdout)
    assert parsed["core_result"]["room_results"][0]["room_id"] == "bedroom"
    assert completed.stderr == ""


def test_standalone_core_keeps_core_action_independent_of_delivery_filters():
    room = DecisionRoom(
        "room",
        "Room",
        Observation(28.0, "°C", NOW, "indoor"),
        Observation(50.0, "%", NOW, "indoor"),
    )
    outdoor = DecisionOutdoor(
        Observation(20.0, "°C", NOW, "outdoor"),
        Observation(50.0, "%", NOW, "outdoor"),
        wind_speed_m_s=Observation(1.0, "m/s", NOW, "outdoor"),
        weather_condition=Observation("clear", "", NOW, "outdoor"),
    )
    result = DecisionEngine().evaluate(
        DecisionSnapshot(
            (room,),
            outdoor,
            NOW,
            context=DecisionContext(quiet_hours_active=True),
        )
    ).room_results[0]
    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.OPEN


def test_ha_delivery_projection_changes_only_delivered_action():
    snapshot = snapshot_from_dict(scenario(indoor=28.0, outdoor=18.0))
    core_result = DecisionEngine().evaluate(snapshot)
    core_room = core_result.room_results[0]
    summary = RecommendationSummary(
        action=RecommendationAction.NONE,
        score=0.0,
        reason="The room window is already open.",
        room_recommendations=(
            RoomRecommendation(
                room_id=core_room.room_id,
                room_name="Bedroom",
                action=RecommendationAction.NONE,
                score=core_room.score,
                reason="The room window is already open.",
                target_perceived_c=core_room.target_perceived_c,
                indoor_perceived_c=core_room.indoor_perceived_c,
                outdoor_perceived_c=core_room.outdoor_perceived_c,
                suggested_comfort_temperature_c=core_room.suggested_comfort_temperature_c,
            ),
        ),
    )
    delivered = build_delivered_result(
        core_result,
        summary,
        {core_room.room_id: "quiet_hours"},
    )
    assert delivered.room_results[0].core_action is core_room.core_action
    assert delivered.room_results[0].delivered_action is RecommendationAction.NONE
