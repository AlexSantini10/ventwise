"""Pure tests for Home Assistant notification delivery policy."""

from ventwise_core import RecommendationAction

from custom_components.ventwise.application.delivery import (
    DeliveryRequest,
    evaluate_delivery,
)


def request(**overrides):
    values = {
        "action": RecommendationAction.OPEN,
        "score": 0.8,
        "notification_enabled": True,
        "channel_available": True,
        "stable_for_seconds": 120,
        "stability_seconds_required": 60,
        "minimum_score": 0.5,
    }
    values.update(overrides)
    return DeliveryRequest(**values)


def test_delivery_allows_a_stable_action_with_an_available_channel():
    assert evaluate_delivery(request()).should_notify is True


def test_quiet_hours_suppress_only_delivery():
    decision = evaluate_delivery(request(quiet_hours_active=True))
    assert decision.should_notify is False
    assert decision.suppressed_by == "quiet_hours"


def test_cooldown_and_duplicate_are_delivery_only_filters():
    assert evaluate_delivery(request(cooldown_active=True)).suppressed_by == "cooldown"
    assert evaluate_delivery(request(duplicate=True)).suppressed_by == "duplicate"


def test_unstable_action_is_not_notified():
    decision = evaluate_delivery(request(stable_for_seconds=10))
    assert decision.should_notify is False
    assert decision.suppressed_by == "stability"


def test_no_recommendation_never_notifies():
    decision = evaluate_delivery(request(action=RecommendationAction.NONE))
    assert decision.should_notify is False
    assert decision.suppressed_by == "no_recommendation"
