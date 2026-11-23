"""Objective composition and aggregation."""

from collections.abc import Iterable

from ..domain.baseline import BaselineAssessment
from ..domain.decision_contracts import DecisionOption, DecisionRoom, DecisionSnapshot
from ..domain.impacts import ImpactEstimate
from ..domain.objectives import ObjectiveAssessment, ObjectiveContribution
from .contracts import Objective


class ObjectiveRegistry:
    """Evaluate objectives in a stable, explicitly configured order."""

    def __init__(self, objectives: Iterable[Objective] = ()) -> None:
        self.objectives = tuple(objectives)

    def assess(
        self,
        room: DecisionRoom,
        snapshot: DecisionSnapshot,
        baseline: BaselineAssessment,
        candidate: DecisionOption,
        impact: ImpactEstimate,
    ) -> ObjectiveAssessment:
        contributions = tuple(
            objective.assess(room, snapshot, baseline, candidate, impact)
            for objective in self.objectives
        )
        confidence = min((item.confidence for item in contributions), default=impact.confidence)
        return ObjectiveAssessment(contributions, confidence)


class ThermalComfortObjective:
    """Assess temperature movement relative to the room comfort target."""

    objective_id = "thermal_comfort"

    def __init__(self, target_temperature_c: float | None = None) -> None:
        self.target_temperature_c = target_temperature_c

    def assess(self, room, snapshot, baseline, candidate, impact) -> ObjectiveContribution:
        indoor = room.temperature_c.value
        target = room.target_temperature_c if room.target_temperature_c is not None else self.target_temperature_c
        if indoor is None or target is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        before = abs(float(indoor) - float(target))
        after = abs(float(indoor) + impact.temperature_delta_c - float(target))
        return ObjectiveContribution(self.objective_id, benefit=max(0.0, before - after), confidence=impact.confidence, reason_code="temperature_improves" if after < before else "temperature_not_improved")


class MoistureExchangeObjective:
    """Assess relative-humidity movement without replacing psychrometric scoring."""

    objective_id = "moisture_exchange"

    def assess(self, room, snapshot, baseline, candidate, impact) -> ObjectiveContribution:
        if room.humidity_percent is None or snapshot.outdoor.humidity_percent is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        benefit = abs(float(impact.humidity_delta_percent)) / 100.0
        return ObjectiveContribution(self.objective_id, benefit=benefit, confidence=impact.confidence, reason_code="humidity_exchange")


class CarbonDioxideObjective:
    """Assess air-quality benefit when a CO2 observation is available."""

    objective_id = "carbon_dioxide"

    def assess(self, room, snapshot, baseline, candidate, impact) -> ObjectiveContribution:
        if room.co2_ppm is None or room.co2_ppm.value is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        benefit = max(0.0, -impact.co2_delta_ppm) / 1000.0
        return ObjectiveContribution(self.objective_id, benefit=benefit, confidence=impact.confidence, reason_code="co2_reduces")
