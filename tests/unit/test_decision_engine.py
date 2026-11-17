"""Tests for the active deterministic decision engine."""

from datetime import datetime, timedelta, timezone

from ventwise_core import (
    Availability,
    DecisionContext,
    DecisionConfig,
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


def test_configured_but_missing_safety_evidence_fails_closed():
    data = snapshot()
    result = DecisionEngine().evaluate(
        DecisionSnapshot(
            data.rooms,
            DecisionOutdoor(
                data.outdoor.temperature_c,
                data.outdoor.humidity_percent,
                safety_evidence_configured=True,
            ),
            NOW,
        )
    ).room_results[0]
    assert result.core_action is RecommendationAction.NONE
    assert result.reason_code == "safety_uncertain"


def test_unknown_configured_contact_never_proves_open_window():
    data = snapshot()
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        window_contact_configured=True,
    )
    result = DecisionEngine().evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]
    assert result.core_action is RecommendationAction.NONE
    assert result.reason_code == "contact_uncertain"


def test_contact_failure_does_not_hide_safety_close():
    data = snapshot(weather="storm")
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        window_contact_configured=True,
    )
    result = DecisionEngine().evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]
    assert result.core_action is RecommendationAction.CLOSE
    assert result.reason_code == "severe_weather"


def test_known_open_window_gets_urgent_close_without_delivery_gates():
    data = snapshot(weather="storm", context=DecisionContext(quiet_hours_active=True, cooldown_active=True, stability_seconds_required=999))
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        window_open=obs(True),
    )
    result = DecisionEngine().evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]
    assert result.core_action is RecommendationAction.CLOSE
    assert result.delivered_action is RecommendationAction.CLOSE
    assert result.urgent is True


def test_co2_is_scored_as_ventilation_influence_without_overriding_safety():
    data = snapshot(indoor=22.0, outdoor=22.0)
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        co2_ppm=obs(1800.0, "ppm"),
    )
    result = DecisionEngine(DecisionConfig(co2_enabled=True)).evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]
    assert result.co2_influence > 0
    assert any(entry.code == "objective.co2" for entry in result.trace)


def test_co2_can_require_ventilation_even_when_outdoor_comfort_is_worse():
    data = snapshot(indoor=22.0, outdoor=35.0)
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        co2_ppm=obs(1200.0, "ppm"),
    )
    result = DecisionEngine(DecisionConfig(co2_enabled=True)).evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]
    assert result.core_action is RecommendationAction.VENTILATE
    assert result.reason_code == "co2_ventilation"


def test_custom_co2_threshold_controls_ventilation_trigger():
    data = snapshot(indoor=22.0, outdoor=22.0)
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        co2_ppm=obs(1300.0, "ppm"),
    )
    engine = DecisionEngine(DecisionConfig(co2_enabled=True, co2_threshold_ppm=1400.0))
    below = engine.evaluate(DecisionSnapshot((room,), data.outdoor, NOW)).room_results[0]
    assert below.core_action is RecommendationAction.NONE

    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        co2_ppm=obs(1500.0, "ppm"),
    )
    above = engine.evaluate(DecisionSnapshot((room,), data.outdoor, NOW)).room_results[0]
    assert above.core_action is RecommendationAction.VENTILATE


def test_default_pressure_is_estimated_and_baseline_is_explicit():
    result = DecisionEngine().evaluate(snapshot()).room_results[0]
    assert result.baseline == "KEEP_CLOSED"
    assert result.quality is Availability.ESTIMATED
    assert any(entry.code == "quality.pressure" for entry in result.trace)
    assert any(entry.code == "component.temperature" for entry in result.component_contributions)
    assert result.evaluated_at == NOW
