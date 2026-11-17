"""Tests for the active deterministic decision engine."""

from datetime import datetime, timedelta, timezone

from ventwise_core import (
    Availability,
    DecisionContext,
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    Validity,
)


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def obs(value, unit=""):
    return Observation(value, unit, NOW, "test")


def snapshot(*, indoor=28.0, outdoor=20.0, weather="clear", context=None):
    return DecisionSnapshot(
        rooms=(DecisionRoom("room", "Room", obs(indoor, "°C"), obs(50.0, "%")),),
        outdoor=DecisionOutdoor(
            obs(outdoor, "°C"),
            obs(50.0, "%"),
            obs(1.0, "m/s"),
            weather_condition=obs(weather),
        ),
        evaluated_at=NOW,
        context=context or DecisionContext(),
    )


def test_same_snapshot_is_reproducible_and_sorts_rooms():
    first = DecisionEngine().evaluate(snapshot())
    second = DecisionEngine().evaluate(snapshot())
    assert first == second
    assert first.room_results[0].core_action is RecommendationAction.OPEN


def test_room_order_does_not_change_aggregate_selection():
    data = snapshot()
    rooms = (
        DecisionRoom("z-room", "Z", obs(28.0, "°C"), obs(50.0, "%")),
        DecisionRoom("a-room", "A", obs(28.0, "°C"), obs(50.0, "%")),
    )
    result = DecisionEngine().evaluate(DecisionSnapshot(rooms, data.outdoor, NOW))
    assert [item.room_id for item in result.room_results] == ["a-room", "z-room"]


def test_stale_critical_input_fails_closed_without_guessing():
    stale = Observation(20.0, "°C", NOW - timedelta(minutes=16), "weather")
    data = snapshot()
    result = DecisionEngine().evaluate(
        DecisionSnapshot(
            data.rooms,
            DecisionOutdoor(stale, data.outdoor.humidity_percent),
            NOW,
        )
    ).room_results[0]
    assert result.core_action is RecommendationAction.NONE
    assert result.reason_code == "insufficient_evidence"
    assert "outdoor.temperature" in result.data_quality.discarded


def test_severe_weather_has_priority_over_comfort():
    result = DecisionEngine().evaluate(snapshot(indoor=22.0, outdoor=22.0, weather="thunderstorm")).room_results[0]
    assert result.core_action is RecommendationAction.CLOSE
    assert result.delivered_action is RecommendationAction.CLOSE
    assert result.reason_code == "severe_weather"


def test_quiet_hours_suppresses_delivery_but_preserves_core_truth():
    result = DecisionEngine().evaluate(
        snapshot(context=DecisionContext(quiet_hours_active=True))
    ).room_results[0]
    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.NONE
    assert result.delivery_suppressed_by == "quiet_hours"


def test_invalid_observation_is_reported():
    invalid = Observation(
        20.0,
        "°C",
        NOW,
        "weather",
        validity=Validity.INVALID,
        availability=Availability.INVALID,
    )
    data = snapshot()
    result = DecisionEngine().evaluate(
        DecisionSnapshot(data.rooms, DecisionOutdoor(invalid, data.outdoor.humidity_percent), NOW)
    ).room_results[0]
    assert result.reason_code == "insufficient_evidence"
    assert "outdoor.temperature" in result.data_quality.discarded
