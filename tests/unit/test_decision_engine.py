"""Focused contract tests for the deterministic decision pipeline."""

from datetime import datetime, timedelta

import pytest

from ventwise_core import (
    Availability,
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    RecommendationContext,
    absolute_humidity_g_m3,
    dew_point_c,
)


NOW = datetime(2026, 11, 9, 12, 0, 0)


def obs(value, unit=""):
    return Observation(value, unit, NOW, NOW, "test")


def snapshot(*, room_temp=28.0, room_humidity=50.0, outdoor_temp=20.0, outdoor_humidity=50.0, weather="clear", wind=1.0, **outdoor):
    return DecisionSnapshot(
        rooms=(DecisionRoom("room", "Room", obs(room_temp, "°C"), obs(room_humidity, "%"), **outdoor.pop("room", {})),),
        outdoor=DecisionOutdoor(obs(outdoor_temp, "°C"), obs(outdoor_humidity, "%"), obs(wind, "m/s"), weather_condition=obs(weather), **outdoor),
        evaluated_at=NOW,
    )


def test_formula_boundaries_use_documented_magnus_equations() -> None:
    assert dew_point_c(20.0, 50.0) == pytest.approx(9.255, abs=0.01)
    assert absolute_humidity_g_m3(20.0, 50.0) == pytest.approx(8.62, abs=0.02)


def test_hot_room_and_comfortable_outdoor_air_is_sustained_open() -> None:
    result = DecisionEngine().evaluate(snapshot()).room_results[0]

    assert result.core_action == RecommendationAction.OPEN
    assert result.delivered_action == RecommendationAction.OPEN
    assert result.reason_code == "thermal_sustained_benefit"
    assert result.trace[0].code == "config.version"


def test_stale_critical_weather_fails_closed() -> None:
    stale = Observation(20.0, "°C", NOW - timedelta(minutes=16), NOW, "weather")
    data = snapshot(outdoor_temp=20.0)
    data = DecisionSnapshot(data.rooms, DecisionOutdoor(stale, data.outdoor.humidity_percent, data.outdoor.wind_speed_m_s, weather_condition=data.outdoor.weather_condition), NOW)

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action == RecommendationAction.NONE
    assert result.reason_code == "critical_weather_unavailable"
    assert "critical_weather_unavailable" in result.blocked_conditions


def test_severe_weather_only_urges_close_when_window_known_open() -> None:
    closed = DecisionEngine().evaluate(snapshot(weather="thunderstorm")).room_results[0]
    opened = DecisionEngine().evaluate(snapshot(weather="thunderstorm", room={"window_open": obs(True)})).room_results[0]

    assert closed.core_action == RecommendationAction.NONE
    assert opened.core_action == RecommendationAction.CLOSE
    assert opened.delivered_action == RecommendationAction.CLOSE


def test_co2_is_targeted_ventilation_not_open_override() -> None:
    result = DecisionEngine().evaluate(snapshot(room_temp=22.0, outdoor_temp=22.0, room={"co2_ppm": obs(1400.0, "ppm")})).room_results[0]

    assert result.core_action == RecommendationAction.VENTILATE
    assert result.duration_minutes == 15


def test_missing_indoor_humidity_does_not_invent_a_value_or_block_thermal_advice() -> None:
    data = snapshot()
    room = data.rooms[0]
    data = DecisionSnapshot(
        (DecisionRoom(room.room_id, room.name, room.temperature_c, Observation(None, "%", None, NOW, "humidity", availability=Availability.AWAITING_SOURCE)),),
        data.outdoor,
        NOW,
    )
    result = DecisionEngine().evaluate(data).room_results[0]
    assert result.core_action == RecommendationAction.OPEN
    assert "indoor.humidity" in result.data_quality.awaiting_source


def test_delivery_suppression_keeps_core_action_and_trace() -> None:
    data = snapshot()
    data = DecisionSnapshot(data.rooms, data.outdoor, NOW, RecommendationContext(quiet_hours_active=True))

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action == RecommendationAction.OPEN
    assert result.delivered_action == RecommendationAction.NONE
    assert result.delivery_suppressed_by == "quiet_hours"
    assert result.trace[-1].code == "delivery.suppressed"


def test_delivery_stability_suppression_keeps_core_action() -> None:
    data = snapshot()
    data = DecisionSnapshot(
        data.rooms,
        data.outdoor,
        NOW,
        RecommendationContext(stable_for_seconds=10, stability_seconds_required=60),
    )
    result = DecisionEngine().evaluate(data).room_results[0]
    assert result.core_action == RecommendationAction.OPEN
    assert result.delivered_action == RecommendationAction.NONE
    assert result.delivery_suppressed_by == "stability"


def test_physical_parameters_only_refine_duration_and_confidence() -> None:
    physical = {
        "volume_m3": 120.0,
        "opening_area_m2": 1.0,
        "opening_fraction": 0.5,
        "thermal_resistance_m2k_w": 2.0,
        "thermal_mass_kj_k": 500.0,
    }
    result = DecisionEngine().evaluate(snapshot(
        room_temp=22.0,
        outdoor_temp=22.0,
        room={"co2_ppm": obs(1400.0, "ppm"), "physical_parameters": tuple(physical.items())},
    )).room_results[0]
    assert result.core_action == RecommendationAction.VENTILATE
    assert result.duration_minutes == 30
    assert result.confidence == 0.9
    assert any(entry.code == "physical.parameters" for entry in result.trace)


def test_awaiting_source_is_explicit_but_never_approximated() -> None:
    data = snapshot(smoke_alert=Observation(None, "", None, None, None, availability=Availability.AWAITING_SOURCE))
    result = DecisionEngine().evaluate(data).room_results[0]

    assert "outdoor.smoke" in result.data_quality.awaiting_source


def test_multi_room_snapshot_keeps_result_order_and_trace_deterministic() -> None:
    """A single event snapshot must always yield the same per-room contract."""

    data = snapshot()
    second_room = DecisionRoom("study", "Study", obs(19.0, "°C"), obs(45.0, "%"))
    multi_room = DecisionSnapshot((data.rooms[0], second_room), data.outdoor, NOW)

    first = DecisionEngine().evaluate(multi_room)
    repeated = DecisionEngine().evaluate(multi_room)

    assert [result.room_id for result in first.room_results] == ["room", "study"]
    assert [result.core_action for result in first.room_results] == [
        result.core_action for result in repeated.room_results
    ]
    assert [[entry.code for entry in result.trace] for result in first.room_results] == [
        [entry.code for entry in result.trace] for result in repeated.room_results
    ]
