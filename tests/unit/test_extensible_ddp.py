"""Tests for the extensible baseline, impact, and objective contracts."""

from datetime import datetime, timezone

from ventwise_core import (
    DecisionEngine,
    DecisionOption,
    DecisionRoom,
    DecisionSnapshot,
    ExternalConditions,
    HeuristicImpactEstimator,
    RecommendationAction,
    ThermalComfortObjective,
    DefaultBaselineAssessor,
    Observation,
    Validity,
)


def _observation(value, unit: str) -> Observation:
    return Observation(
        value=value,
        unit=unit,
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_id="test",
        validity=Validity.VALID,
    )


def _snapshot() -> DecisionSnapshot:
    room = DecisionRoom(
        room_id="bedroom",
        name="Bedroom",
        temperature_c=_observation(26.0, "°C"),
        humidity_percent=_observation(50.0, "%"),
        window_open=_observation(False, "bool"),
        target_temperature_c=22.0,
    )
    outdoor = ExternalConditions(
        temperature_c=_observation(18.0, "°C"),
        humidity_percent=_observation(45.0, "%"),
    )
    return DecisionSnapshot(
        rooms=(room,),
        outdoor=outdoor,
        evaluated_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
    )


def test_baseline_assessor_returns_explicit_closed_state() -> None:
    assessment = DefaultBaselineAssessor().assess(_snapshot().rooms[0])

    assert assessment.state.value == "keep_closed"
    assert assessment.window_state_known is True
    assert assessment.reason_code == "window_known_closed"


def test_heuristic_estimator_reports_directional_opening_impact() -> None:
    snapshot = _snapshot()
    estimate = HeuristicImpactEstimator().estimate(
        snapshot.rooms[0],
        snapshot,
        DecisionOption(RecommendationAction.OPEN, duration_minutes=30),
    )

    assert estimate.temperature_delta_c == -8.0
    assert estimate.horizon_minutes == 30
    assert "directional_effect_only" in estimate.assumptions


def test_engine_attaches_baseline_impact_and_objective_assessments() -> None:
    result = DecisionEngine().evaluate(_snapshot()).room_results[0]

    assert result.option_evaluations
    opening = next(
        item for item in result.option_evaluations
        if item.option.action is RecommendationAction.OPEN
    )
    assert opening.baseline_assessment is not None
    assert opening.impact_estimate is not None
    assert opening.objective_assessment is not None
    assert any(
        contribution.objective_id == ThermalComfortObjective.objective_id
        for contribution in opening.objective_assessment.contributions
    )
