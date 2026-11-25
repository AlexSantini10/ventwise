"""Objective composition and aggregation."""

from collections.abc import Iterable

from ..domain.baseline import BaselineAssessment
from ..domain.decision_contracts import DecisionOption, DecisionRoom, DecisionSnapshot
from ..domain.impacts import ImpactEstimate
from ..domain.objectives import ObjectiveAssessment, ObjectiveContribution
from ..calculations.psychrometrics import (
    absolute_humidity_g_m3,
    humidity_ratio_g_kg,
    pressure_hpa_or_default,
)
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
        if candidate.action.value == "close":
            outdoor = snapshot.outdoor.temperature_c.value
            if outdoor is not None:
                after = before
                before = abs(float(outdoor) - float(target))
        return ObjectiveContribution(self.objective_id, benefit=max(0.0, before - after), confidence=impact.confidence, reason_code="temperature_improves" if after < before else "temperature_not_improved")


class MoistureExchangeObjective:
    """Assess water-content movement without comparing RH across temperatures."""

    objective_id = "moisture_exchange"

    def assess(self, room, snapshot, baseline, candidate, impact) -> ObjectiveContribution:
        if room.humidity_percent is None or snapshot.outdoor.humidity_percent is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        indoor_temperature = room.temperature_c.value
        indoor_humidity = room.humidity_percent.value
        target_humidity = room.target_humidity_percent or 50.0
        if indoor_temperature is None or indoor_humidity is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        indoor_moisture = absolute_humidity_g_m3(float(indoor_temperature), float(indoor_humidity))
        target_moisture = absolute_humidity_g_m3(float(indoor_temperature), float(target_humidity))
        before = abs(indoor_moisture - target_moisture)
        after = abs(indoor_moisture + float(impact.moisture_delta_g_m3) - target_moisture)
        pressure = snapshot.outdoor.pressure_hpa
        pressure_value = pressure.value if pressure is not None else None
        try:
            pressure_hpa, _ = pressure_hpa_or_default(
                float(pressure_value) if pressure_value is not None else None
            )
            indoor_ratio = humidity_ratio_g_kg(
                float(indoor_temperature), float(indoor_humidity), pressure_hpa
            )
            target_ratio = humidity_ratio_g_kg(
                float(indoor_temperature), float(target_humidity), pressure_hpa
            )
            ratio_before = abs(indoor_ratio - target_ratio)
            ratio_after = abs(
                indoor_ratio + float(impact.moisture_delta_g_kg) - target_ratio
            )
            benefit = max(0.0, before - after) / 4.0 + max(
                0.0, ratio_before - ratio_after
            )
        except (TypeError, ValueError):
            benefit = max(0.0, before - after) / 4.0
        reason = "humidity_improves" if after < before else "humidity_not_improved"
        return ObjectiveContribution(self.objective_id, benefit=benefit, confidence=impact.confidence, reason_code=reason)


class CarbonDioxideObjective:
    """Assess air-quality benefit when a CO2 observation is available."""

    objective_id = "carbon_dioxide"

    def __init__(self, threshold_ppm: float = 1000.0, minimum_benefit: float = 0.35) -> None:
        self.threshold_ppm = threshold_ppm
        self.minimum_benefit = minimum_benefit

    def assess(self, room, snapshot, baseline, candidate, impact) -> ObjectiveContribution:
        if room.co2_ppm is None or room.co2_ppm.value is None:
            return ObjectiveContribution(self.objective_id, confidence=0.0)
        excess = max(0.0, float(room.co2_ppm.value) - self.threshold_ppm)
        if excess <= 0.0:
            return ObjectiveContribution(self.objective_id, confidence=impact.confidence, reason_code="co2_below_threshold")
        benefit = self.minimum_benefit + min(0.65, excess / max(self.threshold_ppm, 1.0))
        benefit *= max(0.0, min(1.0, max(0.0, -impact.co2_delta_ppm) / 500.0))
        return ObjectiveContribution(self.objective_id, benefit=benefit, confidence=impact.confidence, reason_code="co2_reduces")
