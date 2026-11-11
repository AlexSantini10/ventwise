"""Focused contract tests for the deterministic decision pipeline."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from ventwise_core import (
    Availability,
    DecisionEngine,
    DecisionConfig,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    RecommendationContext,
    Validity,
    absolute_humidity_g_m3,
    apparent_temperature_c,
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
    assert apparent_temperature_c(26.6, 80.0) == 26.6
    assert apparent_temperature_c(30.0, 39.9) == 30.0
    assert apparent_temperature_c(30.0, 70.0) > 30.0
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


def test_severe_weather_recommends_close_without_window_contact() -> None:
    closed = DecisionEngine().evaluate(snapshot(weather="thunderstorm")).room_results[0]
    opened = DecisionEngine().evaluate(snapshot(weather="thunderstorm", room={"window_open": obs(True)})).room_results[0]

    assert closed.core_action == RecommendationAction.CLOSE
    assert closed.delivered_action == RecommendationAction.CLOSE
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
    assert result.duration_minutes == 15
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


@pytest.mark.parametrize(
    ("name", "data", "action", "reason", "duration", "trace"),
    [
        ("open", snapshot(), RecommendationAction.OPEN, "thermal_sustained_benefit", None, ("score.thermal", "score.moisture", "selection.thermal_sustained_benefit")),
        ("ventilate", snapshot(room_temp=22.0, outdoor_temp=22.0, room={"co2_ppm": obs(1200.0, "ppm")}), RecommendationAction.VENTILATE, "targeted_ventilation_benefit", 15, ("score.thermal", "score.moisture", "selection.targeted_ventilation_benefit")),
        ("close", snapshot(room_temp=19.0, outdoor_temp=31.0, room={"window_open": obs(True)}), RecommendationAction.CLOSE, "outdoor_materially_worse", None, ("score.thermal", "score.moisture", "selection.outdoor_materially_worse")),
        ("none", snapshot(room_temp=22.0, outdoor_temp=22.0), RecommendationAction.NONE, "insufficient_or_tied_benefit", None, ("score.thermal", "score.moisture", "selection.insufficient_or_tied_benefit")),
    ],
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_named_golden_decision_matrix(name, data, action, reason, duration, trace) -> None:
    """Representative golden outputs protect the public action explanation."""

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is action, name
    assert result.delivered_action is action, name
    assert result.reason_code == reason
    assert result.duration_minutes == duration
    assert tuple(entry.code for entry in result.trace[-3:]) == trace
    assert result.candidate_scores.open >= 0.0
    assert result.candidate_scores.ventilate >= 0.0
    assert result.candidate_scores.close >= 0.0


@pytest.mark.parametrize(
    ("label", "outdoor", "expected_block"),
    [
        ("rain_condition", {"weather": "rainy"}, "current_precipitation"),
        ("rain_measurement", {"current_precipitation_mm_h": obs(0.1, "mm/h")}, "current_precipitation"),
        ("thunderstorm", {"weather": "thunderstorm"}, "severe_weather"),
        ("wind", {"wind": DecisionConfig().wind_block_m_s}, "unsafe_wind"),
        ("gust", {"wind_gust_m_s": obs(DecisionConfig().gust_block_m_s, "m/s")}, "unsafe_wind"),
        ("smoke", {"smoke_alert": obs(True)}, "smoke_alert"),
        ("pollen", {"pollen_policy": obs("avoid")}, "outdoor_exposure_avoid"),
        ("pollution", {"pollution_policy": obs("avoid")}, "outdoor_exposure_avoid"),
    ],
)
def test_safety_blocks_override_co2_and_thermal_benefit(label, outdoor, expected_block) -> None:
    """Every safety block wins over a simultaneous thermal/air-quality benefit."""

    data = snapshot(room={"window_open": obs(True), "co2_ppm": obs(1800.0, "ppm")}, **outdoor)
    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.CLOSE, label
    assert result.delivered_action is RecommendationAction.CLOSE, label
    assert expected_block in result.blocked_conditions
    assert result.reason_code == expected_block


@pytest.mark.parametrize(
    ("label", "outdoor", "expected_block"),
    [
        ("rain_condition", {"weather": "rainy"}, "current_precipitation"),
        ("rain_measurement", {"current_precipitation_mm_h": obs(0.1, "mm/h")}, "current_precipitation"),
        ("thunderstorm", {"weather": "thunderstorm"}, "severe_weather"),
        ("wind", {"wind": DecisionConfig().wind_block_m_s}, "unsafe_wind"),
        ("gust", {"wind_gust_m_s": obs(DecisionConfig().gust_block_m_s, "m/s")}, "unsafe_wind"),
        ("smoke", {"smoke_alert": obs(True)}, "smoke_alert"),
        ("pollen", {"pollen_policy": obs("avoid")}, "outdoor_exposure_avoid"),
        ("pollution", {"pollution_policy": obs("avoid")}, "outdoor_exposure_avoid"),
    ],
)
@pytest.mark.parametrize(
    ("window_observation", "expected_delivery_suppression"),
    [
        (obs(True), None),
        (obs(False), "window_already_closed"),
        (None, None),
    ],
    ids=["open", "closed", "unknown-or-unconfigured"],
)
def test_active_safety_blocks_always_close_and_only_suppress_closed_window(
    label, outdoor, expected_block, window_observation, expected_delivery_suppression
) -> None:
    data = snapshot(
        room={"window_open": window_observation, "co2_ppm": obs(1800.0, "ppm")},
        **outdoor,
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.CLOSE, label
    assert result.delivered_action is (
        RecommendationAction.NONE
        if expected_delivery_suppression
        else RecommendationAction.CLOSE
    ), label
    assert result.reason_code == expected_block
    assert expected_block in result.blocked_conditions
    assert result.delivery_suppressed_by == expected_delivery_suppression


def test_active_safety_block_closes_even_when_indoor_temperature_is_missing() -> None:
    data = snapshot(weather="thunderstorm", room={"window_open": None})
    room = data.rooms[0]
    data = replace(
        data,
        rooms=(replace(room, temperature_c=Observation(None, "°C", NOW, NOW, "room", availability=Availability.MISSING)),),
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.CLOSE
    assert result.delivered_action is RecommendationAction.CLOSE
    assert result.reason_code == "severe_weather"


@pytest.mark.parametrize(
    ("label", "observation"),
    [
        ("missing", Observation(None, "°C", NOW, NOW, "test", availability=Availability.MISSING)),
        ("invalid", Observation(20.0, "°C", NOW, NOW, "test", validity=Validity.INVALID, availability=Availability.INVALID)),
        ("disabled", Observation(20.0, "°C", NOW, NOW, "test", availability=Availability.DISABLED_BY_USER)),
        ("stale", Observation(20.0, "°C", NOW - timedelta(minutes=16), NOW, "test")),
        ("future", Observation(20.0, "°C", NOW + timedelta(seconds=1), NOW, "test")),
        ("non_finite", Observation(float("nan"), "°C", NOW, NOW, "test")),
        ("implausible", Observation(80.0, "°C", NOW, NOW, "test")),
    ],
)
def test_unusable_critical_observations_fail_closed(label, observation) -> None:
    data = snapshot()
    data = replace(data, outdoor=replace(data.outdoor, temperature_c=observation))

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.NONE, label
    assert result.reason_code == "critical_weather_unavailable"
    assert "outdoor.temperature" in result.data_quality.discarded


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("co2_ppm", 10_001.0),
        ("wind_speed_m_s", 151.0),
        ("wind_gust_m_s", 151.0),
    ],
)
def test_source_specific_plausibility_bounds_are_rejected(field, value) -> None:
    data = snapshot(room={"co2_ppm": obs(value, "ppm")} if field == "co2_ppm" else {})
    if field != "co2_ppm":
        data = replace(data, outdoor=replace(data.outdoor, **{field: obs(value, "m/s")}))
    result = DecisionEngine().evaluate(data).room_results[0]

    if field == "co2_ppm":
        assert "indoor.co2" in result.data_quality.discarded
    else:
        assert {"wind_speed_m_s": "outdoor.wind", "wind_gust_m_s": "outdoor.gust"}[field] in result.data_quality.discarded


def test_missing_outdoor_humidity_only_removes_moisture_scoring() -> None:
    data = snapshot()
    missing = Observation(None, "%", NOW, NOW, "weather", availability=Availability.MISSING)
    result = DecisionEngine().evaluate(replace(data, outdoor=replace(data.outdoor, humidity_percent=missing))).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert result.candidate_scores.ventilate == 0.0
    assert "outdoor.humidity" in result.data_quality.discarded


def test_thresholds_are_inclusive_and_just_below_remains_eligible() -> None:
    config = DecisionConfig()
    co2_at_threshold = DecisionEngine(config).evaluate(snapshot(room_temp=22.0, outdoor_temp=22.0, room={"co2_ppm": obs(config.co2_threshold_ppm, "ppm")})).room_results[0]
    wind_below_threshold = DecisionEngine(config).evaluate(snapshot(wind=config.wind_block_m_s - 0.001)).room_results[0]

    assert co2_at_threshold.core_action is RecommendationAction.VENTILATE
    assert wind_below_threshold.core_action is RecommendationAction.OPEN


@pytest.mark.parametrize(
    ("label", "data", "expected_action"),
    [
        ("dry_bulb_open", snapshot(room_temp=28.0, outdoor_temp=20.0), RecommendationAction.OPEN),
        ("humid_room_ventilation", snapshot(room_temp=22.0, room_humidity=85.0, outdoor_temp=22.0, outdoor_humidity=40.0), RecommendationAction.VENTILATE),
        ("co2_ventilation", snapshot(room_temp=22.0, outdoor_temp=22.0, room={"co2_ppm": obs(1400.0, "ppm")}), RecommendationAction.VENTILATE),
        ("cold_outdoor_close", snapshot(room_temp=20.0, outdoor_temp=31.0, room={"window_open": obs(True)}), RecommendationAction.CLOSE),
        ("neutral_none", snapshot(room_temp=22.0, outdoor_temp=22.0), RecommendationAction.NONE),
    ],
)
def test_recommendation_matrix_covers_all_core_actions(label, data, expected_action) -> None:
    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is expected_action, label
    assert result.reason_code
    assert all(value >= 0.0 for value in (
        result.candidate_scores.open,
        result.candidate_scores.ventilate,
        result.candidate_scores.close,
    ))


@pytest.mark.parametrize(
    ("window_open", "action", "suppression"),
    [
        (True, RecommendationAction.OPEN, "window_already_open"),
        (True, RecommendationAction.VENTILATE, "window_already_open"),
        (False, RecommendationAction.CLOSE, "window_already_closed"),
    ],
)
def test_window_contacts_suppress_only_already_satisfied_advice(window_open, action, suppression) -> None:
    if action is RecommendationAction.CLOSE:
        data = snapshot(room_temp=20.0, outdoor_temp=31.0, room={"window_open": obs(window_open)})
    else:
        data = snapshot(room_temp=28.0, outdoor_temp=20.0, room={"window_open": obs(window_open)})
        if action is RecommendationAction.VENTILATE:
            data = snapshot(room_temp=22.0, outdoor_temp=22.0, room={"window_open": obs(window_open), "co2_ppm": obs(1400.0, "ppm")})

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is action
    assert result.delivered_action is RecommendationAction.NONE
    assert result.delivery_suppressed_by == suppression


@pytest.mark.parametrize("context_field", ["quiet_hours_active", "cooldown_active"])
def test_delivery_gates_preserve_core_recommendation(context_field) -> None:
    data = snapshot()
    data = replace(data, operational=RecommendationContext(**{context_field: True}))

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.NONE
    assert result.delivery_suppressed_by == context_field.removesuffix("_active")


def test_stability_gate_preserves_core_recommendation() -> None:
    data = replace(
        snapshot(),
        operational=RecommendationContext(stable_for_seconds=10, stability_seconds_required=60),
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.OPEN
    assert result.delivered_action is RecommendationAction.NONE
    assert result.delivery_suppressed_by == "stability"


def test_urgent_safety_close_bypasses_delivery_gates() -> None:
    data = replace(
        snapshot(weather="thunderstorm", room={"window_open": obs(True)}),
        operational=RecommendationContext(quiet_hours_active=True, cooldown_active=True),
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.core_action is RecommendationAction.CLOSE
    assert result.delivered_action is RecommendationAction.CLOSE
    assert result.delivery_suppressed_by is None


def test_forecast_rain_penalizes_opening_and_records_trace() -> None:
    data = snapshot(
        room_temp=28.0,
        outdoor_temp=20.0,
        precipitation_probability_percent=obs(80.0, "%"),
    )

    result = DecisionEngine().evaluate(data).room_results[0]

    assert result.candidate_scores.open == 0.0
    assert "imminent_rain" in result.applied_penalties
    assert any(item.code == "penalty.imminent_rain" for item in result.trace)
