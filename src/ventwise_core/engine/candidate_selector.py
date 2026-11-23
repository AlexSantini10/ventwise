"""Deterministic candidate selection."""

from ..domain.results import CandidateAssessment, SelectionResult


class HighestNetBenefitSelector:
    """Select the allowed candidate with the highest objective net benefit."""

    def select(self, assessments: tuple[CandidateAssessment, ...]) -> SelectionResult:
        allowed = [
            (index, assessment)
            for index, assessment in enumerate(assessments)
            if assessment.allowed and assessment.objectives is not None
        ]
        if not allowed:
            return SelectionResult(None, "no_allowed_candidate")
        selected_index, selected = max(
            allowed,
            key=lambda item: (item[1].objectives.net_benefit, -item[0]),
        )
        return SelectionResult(selected_index, "highest_net_benefit")
