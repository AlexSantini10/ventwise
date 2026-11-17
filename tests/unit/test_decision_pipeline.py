"""Behavioral tests for the active decision pipeline."""

from datetime import datetime, timezone

from ventwise_core import (
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
)


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def observation(value, unit):
    return Observation(value, unit, NOW, "test")


def evaluate(indoor, outdoor, *, indoor_humidity=50.0, outdoor_humidity=50.0, weather="clear"):
    snapshot = DecisionSnapshot(
        rooms=(DecisionRoom("room", "Room", observation(indoor, "°C"), observation(indoor_humidity, "%")),),
        outdoor=DecisionOutdoor(
            observation(outdoor, "°C"),
            observation(outdoor_humidity, "%"),
            weather_condition=observation(weather, ""),
        ),
        evaluated_at=NOW,
    )
    return DecisionEngine().evaluate(snapshot).room_results[0]


def test_hot_room_with_cooler_outdoors_opens():
    assert evaluate(26.0, 21.0).core_action is RecommendationAction.OPEN


def test_crossing_comfort_band_prefers_brief_ventilation():
    assert evaluate(25.0, 18.0).core_action is RecommendationAction.VENTILATE


def test_balanced_conditions_return_none():
    assert evaluate(22.0, 22.0).core_action is RecommendationAction.NONE


def test_severe_weather_forces_close():
    result = evaluate(28.0, 20.0, weather="thunderstorm")
    assert result.core_action is RecommendationAction.CLOSE
    assert result.candidate_scores.close == 1.0


def test_humidity_is_part_of_the_same_decision():
    dry_outdoor = evaluate(24.0, 21.0, indoor_humidity=70.0, outdoor_humidity=30.0)
    humid_outdoor = evaluate(24.0, 21.0, indoor_humidity=70.0, outdoor_humidity=90.0)
    assert dry_outdoor != humid_outdoor
    assert dry_outdoor.reason_code != humid_outdoor.reason_code or dry_outdoor.core_action != humid_outdoor.core_action


def test_reason_and_trace_are_stable_and_sanitized():
    result = evaluate(27.0, 20.0)
    assert result.reason_code
    assert result.trace
    assert all("2026-" not in entry.detail for entry in result.trace)


def test_cold_high_rh_outdoors_can_still_provide_a_drying_moisture_signal():
    result = evaluate(24.0, 5.0, indoor_humidity=50.0, outdoor_humidity=90.0)
    assert any(
        entry.code == "objective.moisture_exchange" and entry.detail == "drying"
        for entry in result.trace
    )


def test_missing_optional_humidity_keeps_thermal_decision_available():
    snapshot = DecisionSnapshot(
        rooms=(DecisionRoom("room", "Room", observation(26.0, "Â°C"), None),),
        outdoor=DecisionOutdoor(observation(20.0, "Â°C"), None),
        evaluated_at=NOW,
    )
    result = DecisionEngine().evaluate(snapshot).room_results[0]
    assert result.core_action is RecommendationAction.OPEN
    assert "indoor.humidity" in result.data_quality.awaiting_source
    assert "outdoor.humidity" in result.data_quality.awaiting_source
