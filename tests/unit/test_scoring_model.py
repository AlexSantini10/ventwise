"""Compatibility coverage for the pre-DDP recommender import."""

from ventwise_core import (
    ComfortObservation,
    ComfortRecommender,
    RecommendationAction,
    RoomObservation,
    RoomProfile,
)


def test_legacy_recommender_facade_delegates_open_decision():
    result = ComfortRecommender().evaluate(
        [RoomProfile("Room", RoomObservation(28.0, 50.0))],
        ComfortObservation(20.0, 50.0),
    )

    assert result.action is RecommendationAction.OPEN
    assert result.room_recommendations[0].reason_code == "comfort_open"


def test_legacy_recommender_facade_delegates_safe_close_decision():
    result = ComfortRecommender().evaluate(
        [RoomProfile("Room", RoomObservation(22.0, 50.0))],
        ComfortObservation(22.0, 50.0, weather_condition="thunderstorm"),
    )

    assert result.action is RecommendationAction.CLOSE
    assert result.room_recommendations[0].reason_code == "severe_weather"
