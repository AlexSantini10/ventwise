"""Comfort recommendation scoring."""

from __future__ import annotations

from typing import Sequence

from .models import (
    ComfortObservation,
    RecommendationAction,
    RecommendationContext,
    RecommendationSummary,
    RoomObservation,
    RoomProfile,
    RoomRecommendation,
    SeasonMode,
    ScoringConfig,
)


def perceived_temperature(
    temperature_c: float,
    humidity_percent: float,
    target_humidity_percent: float,
    humidity_weight: float = 0.04,
) -> float:
    """Return a perceived temperature adjusted for humidity."""

    return temperature_c + ((humidity_percent - target_humidity_percent) * humidity_weight)


def suggested_comfort_temperature(
    target_temperature_c: float,
    indoor_perceived_c: float,
    outdoor_perceived_c: float,
) -> float:
    """Estimate a comfort temperature suggestion from the current conditions."""

    balance_point = (indoor_perceived_c + outdoor_perceived_c) / 2.0
    suggestion = target_temperature_c + ((balance_point - target_temperature_c) * 0.25)
    return _clamp_temperature(suggestion)


class ComfortRecommender:
    """Evaluate room comfort and recommend opening or closing windows."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self._config = config or ScoringConfig()

    @property
    def config(self) -> ScoringConfig:
        """Return the active scoring configuration."""

        return self._config

    def with_config(self, config: ScoringConfig) -> "ComfortRecommender":
        """Create a new recommender with an updated config."""

        return ComfortRecommender(config)

    def evaluate_room(
        self,
        room: RoomProfile,
        outdoor: ComfortObservation,
    ) -> RoomRecommendation:
        """Score one room against the outdoor conditions."""

        target_temperature = (
            room.target_temperature_c_override
            if room.target_temperature_c_override is not None
            else self._config.target_temperature_c
        )
        target_humidity = (
            room.target_humidity_percent_override
            if room.target_humidity_percent_override is not None
            else self._config.target_humidity_percent
        )
        indoor_perceived = perceived_temperature(
            room.indoor.temperature_c,
            room.indoor.humidity_percent,
            target_humidity,
            self._config.humidity_weight,
        )
        outdoor_perceived = perceived_temperature(
            outdoor.temperature_c,
            outdoor.humidity_percent,
            target_humidity,
            self._config.humidity_weight,
        )
        target_perceived = perceived_temperature(
            target_temperature,
            target_humidity,
            target_humidity,
            self._config.humidity_weight,
        )
        suggested_temperature = suggested_comfort_temperature(
            target_perceived,
            indoor_perceived,
            outdoor_perceived,
        )
        inside_delta = abs(indoor_perceived - target_perceived)
        outside_delta = abs(outdoor_perceived - target_perceived)

        if _weather_requires_close(outdoor.weather_condition):
            close_score = self._clamp(max(self._config.minimum_score, 0.75))
            reason = (
                f"{room.name}: weather condition {outdoor.weather_condition} suggests closing windows."
            )
            return RoomRecommendation(
                room_id=room.room_id,
                room_name=room.name,
                action=RecommendationAction.CLOSE,
                score=close_score,
                reason=reason,
                target_perceived_c=target_perceived,
                indoor_perceived_c=indoor_perceived,
                outdoor_perceived_c=outdoor_perceived,
                suggested_comfort_temperature_c=suggested_temperature,
                open_score=0.0,
                close_score=close_score,
            )

        delta = inside_delta - outside_delta
        max_delta = max(inside_delta, outside_delta)
        direction_scale = (
            max(self._config.score_scale_c, max_delta, 1.0)
            if max_delta > 20.0
            else self._config.score_scale_c
        )
        open_score = self._base_direction_score(delta, outdoor, direction_scale)
        close_score = self._base_direction_score(-delta, outdoor, direction_scale)
        open_score, close_score = self._apply_season_bias(open_score, close_score)

        if abs(delta) < self._config.decision_threshold_c:
            action = RecommendationAction.NONE
            score = self._neutral_score(delta)
        elif open_score <= 0.0 and close_score <= 0.0:
            action = RecommendationAction.NONE
            score = 0.0
        elif open_score > close_score:
            action = RecommendationAction.OPEN
            score = open_score
        elif close_score > open_score:
            action = RecommendationAction.CLOSE
            score = close_score
        else:
            action = RecommendationAction.NONE
            score = 0.0

        reason = self._build_reason(
            room.name,
            action,
            indoor_perceived,
            outdoor_perceived,
            inside_delta,
            outside_delta,
            open_score,
            close_score,
        )

        return RoomRecommendation(
            room_id=room.room_id,
            room_name=room.name,
            action=action,
            score=score,
            reason=reason,
            target_perceived_c=target_perceived,
            indoor_perceived_c=indoor_perceived,
            outdoor_perceived_c=outdoor_perceived,
            suggested_comfort_temperature_c=suggested_temperature,
            open_score=open_score,
            close_score=close_score,
        )

    def evaluate(
        self,
        rooms: Sequence[RoomProfile],
        outdoor: ComfortObservation,
        context: RecommendationContext | None = None,
    ) -> RecommendationSummary:
        """Return the best recommendation across all rooms."""

        context = context or RecommendationContext()
        if context.quiet_hours_active:
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason="Quiet hours are active.",
                suggested_comfort_temperature_c=None,
                blocked_by="quiet_hours",
            )
        if context.cooldown_active:
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason="Notification cooldown is active.",
                suggested_comfort_temperature_c=None,
                blocked_by="cooldown",
            )
        if context.stable_for_seconds < self._config.minimum_stability_seconds:
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason=(
                    "Recommendation has not been stable long enough "
                    f"({context.stable_for_seconds}s < {self._config.minimum_stability_seconds}s)."
                ),
                suggested_comfort_temperature_c=None,
                blocked_by="stability",
            )

        active_rooms = tuple(room for room in rooms if room.enabled)
        room_recommendations = tuple(
            self.evaluate_room(room=room, outdoor=outdoor) for room in active_rooms
        )
        if not room_recommendations:
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason="No enabled rooms configured.",
                suggested_comfort_temperature_c=None,
            )

        best_room = max(room_recommendations, key=lambda recommendation: recommendation.score)
        weighted_score = best_room.score
        if (
            best_room.action == RecommendationAction.OPEN
            and outdoor.temperature_c > self._config.soft_outdoor_threshold_c
        ):
            weighted_score *= self._config.soft_threshold_penalty

        weighted_score = self._clamp(weighted_score)
        if weighted_score < self._config.minimum_score or best_room.action == RecommendationAction.NONE:
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=weighted_score,
                reason="The strongest room signal is too small to notify.",
                suggested_comfort_temperature_c=best_room.suggested_comfort_temperature_c,
                room_recommendations=room_recommendations,
                best_room=best_room.room_name,
            )
        return RecommendationSummary(
            action=best_room.action,
            score=weighted_score,
            reason=best_room.reason,
            suggested_comfort_temperature_c=best_room.suggested_comfort_temperature_c,
            room_recommendations=room_recommendations,
            best_room=best_room.room_name,
        )

    def _base_direction_score(
        self,
        delta_c: float,
        outdoor: ComfortObservation,
        scale_c: float,
    ) -> float:
        score = self._clamp(delta_c / scale_c)
        if outdoor.wind_speed_m_s is not None:
            if outdoor.wind_speed_m_s <= self._config.wind_open_preference_threshold_m_s:
                score = self._clamp(
                    score
                    + (outdoor.wind_speed_m_s * self._config.wind_open_preference_per_m_s)
                )
            else:
                score = self._clamp(
                    score
                    - (
                        (
                            outdoor.wind_speed_m_s
                            - self._config.wind_open_preference_threshold_m_s
                        )
                        * self._config.wind_open_penalty_per_m_s
                    )
                )
        return score

    def _neutral_score(self, delta_c: float) -> float:
        return 0.0

    def _build_reason(
        self,
        room_name: str,
        action: RecommendationAction,
        indoor_perceived: float,
        outdoor_perceived: float,
        inside_delta: float,
        outside_delta: float,
        open_score: float,
        close_score: float,
    ) -> str:
        direction = "open" if action == RecommendationAction.OPEN else "close"
        if action == RecommendationAction.NONE:
            direction = "none"
        return (
            f"{room_name}: inside perceived {indoor_perceived:.1f}C is "
            f"{inside_delta:.1f}C from target, outside perceived {outdoor_perceived:.1f}C is "
            f"{outside_delta:.1f}C from target, open={open_score:.2f}, close={close_score:.2f}, "
            f"so action={direction}."
        )

    def _apply_season_bias(self, open_score: float, close_score: float) -> tuple[float, float]:
        if abs(open_score - close_score) > 0.05:
            return open_score, close_score

        if self._config.season_mode == SeasonMode.SUMMER:
            open_score += max(self._config.open_bias, 0.02)
        elif self._config.season_mode == SeasonMode.WINTER:
            close_score += max(self._config.close_bias, 0.02)
        else:
            open_score += self._config.open_bias
            close_score += self._config.close_bias
        return self._clamp(open_score), self._clamp(close_score)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))


def _clamp_temperature(value: float) -> float:
    return max(10.0, min(30.0, value))


def _weather_requires_close(weather_condition: str | None) -> bool:
    if weather_condition is None:
        return False
    lowered = weather_condition.strip().lower()
    return any(token in lowered for token in ("thunder", "lightning", "storm", "hail"))
