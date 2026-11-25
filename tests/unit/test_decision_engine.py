"""Tests for the active deterministic decision engine."""

from datetime import datetime, timedelta, timezone

from ventwise_core import (
    Availability,
    DecisionRuntimeContext,
    DecisionConfig,
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    ObjectiveContribution,
    RecommendationAction,
    RoomGuardrailState,
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
        context=context or DecisionRuntimeContext(),
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


def test_quiet_hours_does_not_change_core_result():
    result = DecisionEngine().evaluate(
        snapshot(context=DecisionRuntimeContext(quiet_hours_active=True))
    ).room_results[0]
    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.OPEN
    assert result.delivery_suppressed_by is None


def test_window_state_suppresses_already_satisfied_open_action():
    data = snapshot()
    room = DecisionRoom(
        "room", "Room", data.rooms[0].temperature_c, data.rooms[0].humidity_percent,
        window_open=obs(True),
    )
    result = DecisionEngine().evaluate(DecisionSnapshot((room,), data.outdoor, NOW)).room_results[0]
    assert result.core_action is RecommendationAction.NONE
    assert result.reason_code == "window_already_open"
    assert any(entry.code == "selection.window_already_open" for entry in result.trace)


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


def test_missing_timestamp_is_not_treated_as_current():
    data = snapshot()
    missing_timestamp = Observation(20.0, "Â°C", None, "weather")
    result = DecisionEngine().evaluate(
        DecisionSnapshot(data.rooms, DecisionOutdoor(missing_timestamp, data.outdoor.humidity_percent), NOW)
    ).room_results[0]

    assert result.core_action is RecommendationAction.NONE
    assert "outdoor.temperature:missing_timestamp" in result.data_quality.discarded_reasons


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
    data = snapshot(weather="storm", context=DecisionRuntimeContext(quiet_hours_active=True, cooldown_active=True, stability_seconds_required=999))
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


def test_calculated_co2_recommendation_remains_visible_during_stabilization():
    """The immediate core result is distinct from the stabilized result."""

    data = snapshot(indoor=23.0, outdoor=15.0, weather="rainy")
    room = DecisionRoom(
        "room",
        "Room",
        data.rooms[0].temperature_c,
        data.rooms[0].humidity_percent,
        co2_ppm=obs(2000.0, "ppm"),
        action_change_hold_seconds=5 * 60,
    )
    config = DecisionConfig(co2_enabled=True, target_temperature_c=19.9)
    stabilized = DecisionEngine(config).evaluate(
        DecisionSnapshot(
            (room,),
            data.outdoor,
            NOW,
            DecisionRuntimeContext(
                room_guardrails=(RoomGuardrailState("room", RecommendationAction.NONE.value),)
            ),
        )
    ).room_results[0]
    calculated = DecisionEngine(config).evaluate(
        DecisionSnapshot((room,), data.outdoor, NOW)
    ).room_results[0]

    assert calculated.core_action is RecommendationAction.VENTILATE
    assert calculated.reason_code == "co2_ventilation"
    assert stabilized.core_action is RecommendationAction.NONE
    assert stabilized.reason_code == "action_hold"


def test_default_pressure_is_estimated_and_baseline_is_explicit():
    result = DecisionEngine().evaluate(snapshot()).room_results[0]
    assert result.baseline == "KEEP_CLOSED"
    assert result.quality is Availability.ESTIMATED
    assert any(entry.code == "quality.pressure" for entry in result.trace)
    assert any(entry.code == "component.temperature" for entry in result.component_contributions)
    assert result.evaluated_at == NOW


def test_result_contains_one_structured_evaluation_per_decision_option():
    result = DecisionEngine().evaluate(snapshot()).room_results[0]

    assert [item.option.action for item in result.option_evaluations] == [
        RecommendationAction.OPEN,
        RecommendationAction.VENTILATE,
        RecommendationAction.CLOSE,
        RecommendationAction.NONE,
    ]
    assert sum(item.selected for item in result.option_evaluations) == 1
    assert next(
        item for item in result.option_evaluations
        if item.option.action is RecommendationAction.OPEN
    ).score == result.candidate_scores.open


def test_configured_objective_selector_controls_the_core_action():
    class PreferVentilation:
        objective_id = "test_prefer_ventilation"

        def assess(self, room, snapshot, baseline, candidate, impact):
            return ObjectiveContribution(
                self.objective_id,
                benefit=1.0 if candidate.action is RecommendationAction.VENTILATE else 0.0,
                confidence=1.0,
            )

    result = DecisionEngine(objectives=(PreferVentilation(),)).evaluate(
        snapshot(indoor=22.0, outdoor=22.0)
    ).room_results[0]

    assert result.core_action is RecommendationAction.VENTILATE
    assert result.selection_reason_code == "highest_net_benefit"


def test_pipeline_components_can_be_replaced_without_changing_result_contract():
    class OnlyNoneGenerator:
        def generate(self, context):
            from ventwise_core import DecisionOption

            return (DecisionOption(RecommendationAction.NONE),)

    result = DecisionEngine(option_generator=OnlyNoneGenerator()).evaluate(snapshot()).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert len(result.option_evaluations) == 1
    assert result.option_evaluations[0].option.action is RecommendationAction.NONE
