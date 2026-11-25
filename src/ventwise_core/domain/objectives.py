"""Objective assessment contracts."""

from dataclasses import dataclass

from .decision_contracts import TraceEntry


@dataclass(frozen=True, slots=True)
class ObjectiveContribution:
    """One objective's normalized contribution for a candidate."""

    objective_id: str
    benefit: float = 0.0
    cost: float = 0.0
    weight: float = 1.0
    confidence: float = 0.0
    reason_code: str = "not_applicable"
    evidence: tuple[TraceEntry, ...] = ()

    @property
    def net_benefit(self) -> float:
        """Return the weighted net contribution."""

        return (self.benefit - self.cost) * self.weight


@dataclass(frozen=True, slots=True)
class ObjectiveAssessment:
    """Combined, inspectable result of the configured objectives."""

    contributions: tuple[ObjectiveContribution, ...] = ()
    confidence: float = 0.0

    @property
    def net_benefit(self) -> float:
        """Return the sum of all objective contributions."""

        return sum(item.net_benefit for item in self.contributions)
