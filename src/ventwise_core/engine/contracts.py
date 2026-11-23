"""Variation-point contracts for the deterministic decision pipeline."""

from typing import Protocol

from ..domain.baseline import BaselineAssessment
from ..domain.decision_contracts import DecisionOption, DecisionRoom, DecisionSnapshot, OptionEligibility
from ..domain.impacts import ImpactEstimate
from ..domain.objectives import ObjectiveAssessment, ObjectiveContribution
from ..domain.results import CandidateAssessment, SelectionResult


class BaselineAssessor(Protocol):
    """Assess the state maintained when no candidate is selected."""

    def assess(self, room: DecisionRoom) -> BaselineAssessment: ...


class ImpactEstimator(Protocol):
    """Estimate the environmental effect of one candidate."""

    def estimate(
        self,
        room: DecisionRoom,
        snapshot: DecisionSnapshot,
        candidate: DecisionOption,
    ) -> ImpactEstimate: ...


class ConstraintPolicy(Protocol):
    """Evaluate hard and soft constraints before objectives run."""

    def evaluate(
        self,
        room: DecisionRoom,
        snapshot: DecisionSnapshot,
        candidate: DecisionOption,
    ) -> OptionEligibility: ...


class Objective(Protocol):
    """Assess one independent comfort or air-quality objective."""

    objective_id: str

    def assess(
        self,
        room: DecisionRoom,
        snapshot: DecisionSnapshot,
        baseline: BaselineAssessment,
        candidate: DecisionOption,
        impact: ImpactEstimate,
    ) -> ObjectiveContribution: ...


class CandidateSelector(Protocol):
    """Select one candidate from complete assessments."""

    def select(self, assessments: tuple[CandidateAssessment, ...]) -> SelectionResult: ...
