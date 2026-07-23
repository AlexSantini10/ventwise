"""Tests for the comfort scoring core."""

from ventwise_core import (
    ComfortObservation,
    ComfortRecommender,
    RecommendationAction,
    RecommendationContext,
    RoomObservation,
    RoomProfile,
    SeasonMode,
    ScoringConfig,
)


def test_recommender_prefers_open_when_outside_is_more_comfortable() -> None:
    recommender = ComfortRecommender(ScoringConfig(target_temperature_c=22.0))
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=26.0, humidity_percent=60.0),
    )
    outdoor = ComfortObservation(temperature_c=21.0, humidity_percent=55.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.OPEN
    assert result.score > 0
    assert result.best_room == "Camera"


def test_recommender_prefers_close_when_inside_is_more_comfortable() -> None:
    recommender = ComfortRecommender()
    room = RoomProfile(
        room_id="room-1",
        name="Salotto",
        indoor=RoomObservation(temperature_c=22.2, humidity_percent=45.0),
    )
    outdoor = ComfortObservation(temperature_c=29.0, humidity_percent=65.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.CLOSE
    assert result.score > 0


def test_recommender_returns_none_for_neutral_conditions() -> None:
    recommender = ComfortRecommender()
    room = RoomProfile(
        room_id="room-1",
        name="Studio",
        indoor=RoomObservation(temperature_c=22.1, humidity_percent=50.0),
    )
    outdoor = ComfortObservation(temperature_c=22.0, humidity_percent=50.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.NONE
    assert result.score == 0


def test_recommender_applies_soft_outdoor_threshold_to_open_actions() -> None:
    recommender = ComfortRecommender(
        ScoringConfig(target_temperature_c=22.0, minimum_score=0.0)
    )
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=28.0, humidity_percent=55.0),
    )
    cool_outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)
    warm_outdoor = ComfortObservation(temperature_c=24.0, humidity_percent=45.0)

    cool_result = recommender.evaluate([room], cool_outdoor)
    warm_result = recommender.evaluate([room], warm_outdoor)

    assert cool_result.action == RecommendationAction.OPEN
    assert warm_result.action == RecommendationAction.OPEN
    assert warm_result.score < cool_result.score


def test_recommender_penalizes_strong_wind_for_open_actions() -> None:
    recommender = ComfortRecommender(
        ScoringConfig(target_temperature_c=22.0, minimum_score=0.0)
    )
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=28.0, humidity_percent=55.0),
    )
    calm_outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0, wind_speed_m_s=1.0)
    windy_outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0, wind_speed_m_s=20.0)

    calm_result = recommender.evaluate([room], calm_outdoor)
    windy_result = recommender.evaluate([room], windy_outdoor)

    assert calm_result.action == RecommendationAction.OPEN
    assert windy_result.action != RecommendationAction.OPEN
    assert windy_result.score < calm_result.score


def test_recommender_blocks_until_stable() -> None:
    recommender = ComfortRecommender(
        ScoringConfig(minimum_stability_seconds=600, minimum_score=0.0)
    )
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=28.0, humidity_percent=55.0),
    )
    outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)

    result = recommender.evaluate(
        [room],
        outdoor,
        RecommendationContext(stable_for_seconds=120),
    )

    assert result.action == RecommendationAction.NONE
    assert result.blocked_by == "stability"


def test_recommender_can_be_hint_tuned_for_winter() -> None:
    recommender = ComfortRecommender(
        ScoringConfig(season_mode=SeasonMode.WINTER, minimum_score=0.0, neutral_band_c=0.0)
    )
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=22.28, humidity_percent=50.0),
    )
    outdoor = ComfortObservation(temperature_c=22.20, humidity_percent=50.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.CLOSE
    assert result.best_room == "Camera"


def test_recommender_returns_none_for_quiet_hours() -> None:
    recommender = ComfortRecommender()
    room = RoomProfile(
        room_id="room-1",
        name="Salotto",
        indoor=RoomObservation(temperature_c=27.0, humidity_percent=60.0),
    )
    outdoor = ComfortObservation(temperature_c=18.0, humidity_percent=45.0)

    result = recommender.evaluate(
        [room],
        outdoor,
        RecommendationContext(quiet_hours_active=True),
    )

    assert result.action == RecommendationAction.NONE
    assert result.blocked_by == "quiet_hours"


def test_recommender_prefers_the_best_room_by_score() -> None:
    recommender = ComfortRecommender(
        ScoringConfig(target_temperature_c=22.0, minimum_score=0.0)
    )
    rooms = [
        RoomProfile(
            room_id="room-1",
            name="Studio",
            indoor=RoomObservation(temperature_c=30.0, humidity_percent=55.0),
        ),
        RoomProfile(
            room_id="room-2",
            name="Kitchen",
            indoor=RoomObservation(temperature_c=27.5, humidity_percent=60.0),
        ),
    ]
    outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)

    result = recommender.evaluate(rooms, outdoor)

    assert result.action == RecommendationAction.OPEN
    assert result.best_room == "Studio"
    assert len(result.room_recommendations) == 2
    assert result.room_recommendations[0].room_name == "Studio"


def test_recommender_returns_none_when_no_rooms_are_configured() -> None:
    recommender = ComfortRecommender()
    outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)

    result = recommender.evaluate([], outdoor)

    assert result.action == RecommendationAction.NONE
    assert result.reason == "No enabled rooms configured."


def test_recommender_honors_room_target_override() -> None:
    recommender = ComfortRecommender(ScoringConfig(target_temperature_c=22.0, minimum_score=0.0))
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=24.0, humidity_percent=50.0),
        target_temperature_c_override=24.0,
    )
    outdoor = ComfortObservation(temperature_c=24.0, humidity_percent=50.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.NONE


def test_recommender_skips_disabled_rooms() -> None:
    recommender = ComfortRecommender()
    room = RoomProfile(
        room_id="room-1",
        name="Camera",
        indoor=RoomObservation(temperature_c=28.0, humidity_percent=60.0),
        enabled=False,
    )
    outdoor = ComfortObservation(temperature_c=20.0, humidity_percent=45.0)

    result = recommender.evaluate([room], outdoor)

    assert result.action == RecommendationAction.NONE
    assert result.reason == "No enabled rooms configured."
