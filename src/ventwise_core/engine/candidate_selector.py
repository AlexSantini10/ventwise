"""Deterministic candidate selection."""

from ..domain.results import CandidateAssessment, SelectionResult
from ..domain.decision_contracts import RecommendationAction


class HighestNetBenefitSelector:
    """Select the allowed candidate with the highest objective net benefit."""

    def __init__(self, *, minimum_benefit: float = 0.35, winner_margin: float = 0.05) -> None:
        self.minimum_benefit = minimum_benefit
        self.winner_margin = winner_margin

    def select(self, assessments: tuple[CandidateAssessment, ...]) -> SelectionResult:
        allowed = [
            (index, assessment)
            for index, assessment in enumerate(assessments)
            if assessment.allowed and assessment.objectives is not None
        ]
        if not allowed:
            return SelectionResult(None, "no_allowed_candidate")
        none = next(
            ((index, assessment) for index, assessment in allowed if assessment.candidate.action is RecommendationAction.NONE),
            None,
        )
        actionable = [
            item for item in allowed if item[1].candidate.action is not RecommendationAction.NONE
        ]
        if not actionable:
            return SelectionResult(none[0] if none else None, "no_actionable_candidate")

        selected_index, selected = max(
            actionable,
            key=lambda item: (item[1].objectives.net_benefit, -item[0]),
        )
        selected_benefit = selected.objectives.net_benefit
        if selected_benefit < self.minimum_benefit:
            return SelectionResult(none[0] if none else None, "insufficient_benefit")

        runner_up = max(
            (assessment.objectives.net_benefit for index, assessment in actionable if index != selected_index),
            default=0.0,
        )
        if selected_benefit - runner_up < self.winner_margin:
            return SelectionResult(none[0] if none else None, "insufficient_or_tied_benefit")
        return SelectionResult(selected_index, "highest_net_benefit")
