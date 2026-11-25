"""Structured candidate and selection results."""

from dataclasses import dataclass

from .baseline import BaselineAssessment
from .decision_contracts import DecisionOption, OptionEligibility
from .impacts import ImpactEstimate
from .objectives import ObjectiveAssessment


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    """Complete assessment of one candidate before final selection."""

    candidate: DecisionOption
    eligibility: OptionEligibility
    impact: ImpactEstimate | None
    objectives: ObjectiveAssessment | None
    baseline: BaselineAssessment

    @property
    def allowed(self) -> bool:
        """Whether constraints permit this candidate."""

        return self.eligibility.allowed


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Deterministic candidate selection outcome."""

    selected_index: int | None
    reason_code: str
