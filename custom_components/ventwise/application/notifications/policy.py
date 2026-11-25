"""Pure notification-delivery policy for the Home Assistant adapter.

The decision core owns the recommended action.  This module owns only the
question whether that already-computed recommendation may be notified now.
Keeping this policy pure makes quiet hours, stability and cooldown behavior
testable without Home Assistant or a running notifier service.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ...ventwise_core import RecommendationAction
except ImportError:  # Local source-tree development uses the standalone package.
    from ventwise_core import RecommendationAction


@dataclass(frozen=True, slots=True)
class DeliveryRequest:
    """Inputs required to decide notification eligibility for one room."""

    action: RecommendationAction
    score: float
    notification_enabled: bool
    channel_available: bool
    quiet_hours_active: bool = False
    cooldown_active: bool = False
    stable_for_seconds: int = 0
    stability_seconds_required: int = 0
    duplicate: bool = False
    minimum_score: float = 0.0
    is_safety: bool = False
    safety_bypasses_quiet_hours: bool = False


@dataclass(frozen=True, slots=True)
class DeliveryDecision:
    """Delivery outcome; it never contains an alternative domain action."""

    should_notify: bool
    suppressed_by: str | None = None


def evaluate_delivery(request: DeliveryRequest) -> DeliveryDecision:
    """Apply adapter-only notification filters in a deterministic order."""

    if request.action is RecommendationAction.NONE:
        return DeliveryDecision(False, "no_recommendation")
    if not request.notification_enabled or not request.channel_available:
        return DeliveryDecision(False, "notification_channel")
    if request.duplicate:
        return DeliveryDecision(False, "duplicate")
    if request.quiet_hours_active:
        if not (request.is_safety and request.safety_bypasses_quiet_hours):
            return DeliveryDecision(False, "quiet_hours")
    if (
        not request.is_safety
        and request.stable_for_seconds < request.stability_seconds_required
    ):
        return DeliveryDecision(False, "stability")
    if request.cooldown_active and not request.is_safety:
        return DeliveryDecision(False, "cooldown")
    if request.score < request.minimum_score:
        return DeliveryDecision(False, "minimum_score")
    return DeliveryDecision(True)
