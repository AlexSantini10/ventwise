"""Small, explicit variation points for the decision pipeline.

The v0.18 engine remains the compatibility implementation.  These contracts
make each option's evaluation inspectable and provide narrow seams for future
forecast, calibrated-estimator, and policy work.
"""

from __future__ import annotations

from typing import Protocol

from .models import (
    CandidateScores,
    DecisionEvaluationContext,
    DecisionOption,
    ExpectedEffect,
    OptionEligibility,
    OptionEvaluation,
    RecommendationAction,
    TraceEntry,
)


class DecisionOptionGenerator(Protocol):
    """Generate the deterministic set of actions to compare."""

    def generate(self, context: DecisionEvaluationContext) -> tuple[DecisionOption, ...]: ...


class OptionEligibilityPolicy(Protocol):
    """Decide whether one action is safe and permitted."""

    def check(
        self, context: DecisionEvaluationContext, option: DecisionOption
    ) -> OptionEligibility: ...


class ExpectedEffectEstimator(Protocol):
    """Describe the expected environmental effect of one action."""

    def estimate(
        self,
        context: DecisionEvaluationContext,
        option: DecisionOption,
        horizon_minutes: int,
    ) -> ExpectedEffect: ...


class DecisionOptionScorer(Protocol):
    """Turn eligibility and expected effect into an option evaluation."""

    def evaluate(
        self,
        context: DecisionEvaluationContext,
        option: DecisionOption,
        eligibility: OptionEligibility,
        expected_effect: ExpectedEffect,
    ) -> OptionEvaluation: ...


class DefaultDecisionOptionGenerator:
    """The fixed v0.18 action set, in stable selection order."""

    def generate(self, context: DecisionEvaluationContext) -> tuple[DecisionOption, ...]:
        return tuple(DecisionOption(action) for action in (
            RecommendationAction.OPEN,
            RecommendationAction.VENTILATE,
            RecommendationAction.CLOSE,
            RecommendationAction.NONE,
        ))


class TraceOptionEligibilityPolicy:
    """Project existing v0.18 safety trace entries into structured eligibility."""

    def check(
        self, context: DecisionEvaluationContext, option: DecisionOption
    ) -> OptionEligibility:
        blocks = tuple(entry for entry in context.trace if entry.code.startswith("block."))
        uncertain = any(
            entry.code in {"selection.safety_uncertain", "selection.contact_uncertain"}
            for entry in context.trace
        )
        opening = option.action in {RecommendationAction.OPEN, RecommendationAction.VENTILATE}
        if opening and (blocks or uncertain):
            evidence = blocks or tuple(
                entry for entry in context.trace if entry.code in {
                    "selection.safety_uncertain", "selection.contact_uncertain"
                }
            )
            return OptionEligibility(False, evidence, reason_code=evidence[0].code)
        return OptionEligibility(True)


class TraceExpectedEffectEstimator:
    """Expose current component/objective trace entries as effect evidence."""

    def estimate(
        self,
        context: DecisionEvaluationContext,
        option: DecisionOption,
        horizon_minutes: int,
    ) -> ExpectedEffect:
        evidence = tuple(entry for entry in context.trace if entry.code.startswith((
            "component.", "objective.", "penalty."
        )))
        return ExpectedEffect(confidence=1.0 if evidence else 0.0, evidence=evidence)


class ScoreFromV018Result:
    """Preserve v0.18 scores while exposing them as option evaluations."""

    @staticmethod
    def _score(scores: CandidateScores | None, action: RecommendationAction) -> float:
        if scores is None:
            return 0.0
        return {
            RecommendationAction.OPEN: scores.open,
            RecommendationAction.VENTILATE: scores.ventilate,
            RecommendationAction.CLOSE: scores.close,
            RecommendationAction.NONE: scores.none,
        }[action]

    def evaluate(
        self,
        context: DecisionEvaluationContext,
        option: DecisionOption,
        eligibility: OptionEligibility,
        expected_effect: ExpectedEffect,
    ) -> OptionEvaluation:
        score = self._score(context.candidate_scores, option.action)
        selected = option.action is context.selected_action
        return OptionEvaluation(
            option=option,
            eligibility=eligibility,
            expected_effect=expected_effect,
            score=score if eligibility.allowed else 0.0,
            confidence=expected_effect.confidence if eligibility.allowed else 0.0,
            selected=selected,
            reason_code=(
                "selected" if selected
                else eligibility.reason_code if not eligibility.allowed
                else "not_selected"
            ),
        )
