"""Contract tests for the minimal deterministic decision pipeline."""

from datetime import datetime, timedelta, timezone

import pytest

from ventwise_core import (
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    absolute_humidity_g_m3,
)


NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def obs(value, unit=""):
    return Observation(value, unit, NOW, NOW, "test")


def snapshot(*, indoor=28.0, outdoor=20.0, weather="clear", context=None):
    return DecisionSnapshot(
        rooms=(DecisionRoom("room", "Room", obs(indoor, "°C"), obs(50.0, "%")),),
        outdoor=DecisionOutdoor(
            obs(outdoor, "°C"), obs(50.0, "%"), obs(1.0, "m/s"), weather_condition=obs(weather)
        ),
        evaluated_at=NOW,
        context=context or DecisionContext(),
    )


def test_same_snapshot_produces_same_result_and_trace():
    engine = DecisionEngine()

    first = engine.evaluate(snapshot())
    second = engine.evaluate(snapshot())

    assert first == second
    assert first.room_results[0].core_action is RecommendationAction.OPEN
    assert first.trace == (first.trace[0],)


def test_room_order_is_stable_for_aggregate_selection():
    data = snapshot()
    rooms = (
        DecisionRoom("z-room", "Z", obs(28.0, "°C"), obs(50.0, "%")),
        DecisionRoom("a-room", "A", obs(28.0, "°C"), obs(50.0, "%")),
    )
    reordered = DecisionSnapshot(rooms, data.outdoor, NOW)

    result = DecisionEngine().evaluate(reordered)

    assert [item.room_id for item in result.room_results] == ["a-room", "z-room"]
    assert result.trace[0].detail == "a-room"


def test_stale_critical_input_returns_none_without_guessing():
    stale = Observation(20.0, "°C", NOW - timedelta(minutes=16), NOW, "weather")
    data = snapshot()
    data = DecisionSnapshot(
        data.rooms,
        DecisionOutdoor(stale, data.outdoor.humidity_percent, data.outdoor.wind_speed_m_s, weather_condition=data.outdoor.weather_condition),
        NOW,
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.NONE
    assert result.reason_code == "insufficient_evidence"
    assert "outdoor.temperature" in result.data_quality.discarded


def test_weather_block_preserves_core_close_and_delivery_contract():
    data = snapshot(indoor=22.0, outdoor=22.0, weather="thunderstorm")

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.CLOSE
    assert result.delivered_action is RecommendationAction.CLOSE
    assert result.reason_code == "severe_weather"


def test_crossing_the_comfort_band_returns_brief_ventilation():
    data = snapshot(indoor=25.0, outdoor=18.0)

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.VENTILATE
    assert result.delivered_action is RecommendationAction.VENTILATE


def test_delivery_gate_suppresses_delivery_without_changing_core_truth():
    data = snapshot(context=DecisionContext(quiet_hours_active=True))

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.NONE
    assert result.delivery_suppressed_by == "quiet_hours"


def test_engine_has_no_wall_clock_dependency():
    data = snapshot()
    engine = DecisionEngine(DecisionConfig())

    result = engine.evaluate(data).room_results[0]

    assert result.trace[0].code == "config.version"
    assert all("2026-" not in item.detail for item in result.trace)


def test_absolute_humidity_uses_magnus_equation() -> None:
    assert absolute_humidity_g_m3(20.0, 50.0) == pytest.approx(8.65, abs=0.05)


def test_moisture_only_drying_recommends_ten_minute_ventilation() -> None:
    data = snapshot(indoor=22.0, outdoor=22.0)
    room = DecisionRoom("room", "Room", obs(22.0, "°C"), obs(70.0, "%"))
    outdoor = DecisionOutdoor(obs(22.0, "°C"), obs(40.0, "%"), weather_condition=obs("clear"))
    result = DecisionEngine().evaluate(DecisionSnapshot((room,), outdoor, NOW)).room_results[0]

    assert result.core_action is RecommendationAction.VENTILATE
    assert result.reason_code == "moisture_drying"
    assert result.moisture_delta_g_m3 is not None and result.moisture_delta_g_m3 >= 1.0
    assert any(item.code == "moisture.direction" and item.detail == "drying" for item in result.trace)


def test_missing_humidity_preserves_temperature_recommendation() -> None:
    data = snapshot()
    room = DecisionRoom("room", "Room", obs(28.0, "°C"), None)
    result = DecisionEngine().evaluate(DecisionSnapshot((room,), data.outdoor, NOW)).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert result.moisture_delta_g_m3 is None
    assert "indoor.humidity.missing" in result.data_quality.diagnostics
