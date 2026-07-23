"""Comfort recommendation scoring."""

from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)


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
            if room.target_temperature_c_override_enabled
            and room.target_temperature_c_override is not None
            else self._config.target_temperature_c
        )
        target_humidity = (
            room.target_humidity_percent_override
            if room.target_humidity_percent_override_enabled
            and room.target_humidity_percent_override is not None
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
            _LOGGER.debug(
                "Recommendation decision for room %s: action=%s score=%.2f reason=%s "
                "target_perceived=%.2f indoor_perceived=%.2f outdoor_perceived=%.2f",
                room.name,
                RecommendationAction.CLOSE.value,
                close_score,
                reason,
                target_perceived,
                indoor_perceived,
                outdoor_perceived,
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

        open_score = self._direction_score(
            need_c=inside_delta,
            benefit_c=max(0.0, inside_delta - outside_delta),
            outdoor=outdoor,
            direction=RecommendationAction.OPEN,
        )
        close_score = self._direction_score(
            need_c=outside_delta,
            benefit_c=max(0.0, outside_delta - inside_delta),
            outdoor=outdoor,
            direction=RecommendationAction.CLOSE,
        )
        open_score, close_score = self._apply_season_bias(open_score, close_score)
        target_penalty = self._target_reasonableness_factor(target_temperature, target_humidity)
        open_score = self._clamp(open_score * target_penalty)
        close_score = self._clamp(close_score * target_penalty)

        if max(inside_delta, outside_delta) < self._config.decision_threshold_c:
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
        _LOGGER.debug(
            "Recommendation decision for room %s: action=%s score=%.2f reason=%s "
            "target_perceived=%.2f indoor_perceived=%.2f outdoor_perceived=%.2f "
            "open_score=%.2f close_score=%.2f inside_delta=%.2f outside_delta=%.2f",
            room.name,
            action.value,
            score,
            reason,
            target_perceived,
            indoor_perceived,
            outdoor_perceived,
            open_score,
            close_score,
            inside_delta,
            outside_delta,
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
            _LOGGER.debug(
                "Recommendation summary blocked: quiet hours active, action=%s score=0.00",
                RecommendationAction.NONE.value,
            )
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason="Quiet hours are active.",
                suggested_comfort_temperature_c=None,
                blocked_by="quiet_hours",
            )
        if context.cooldown_active:
            _LOGGER.debug(
                "Recommendation summary blocked: cooldown active, action=%s score=0.00",
                RecommendationAction.NONE.value,
            )
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=0.0,
                reason="Notification cooldown is active.",
                suggested_comfort_temperature_c=None,
                blocked_by="cooldown",
            )
        if context.stable_for_seconds < self._config.minimum_stability_seconds:
            _LOGGER.debug(
                "Recommendation summary blocked: stability=%ss below threshold=%ss, action=%s score=0.00",
                context.stable_for_seconds,
                self._config.minimum_stability_seconds,
                RecommendationAction.NONE.value,
            )
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
            _LOGGER.debug(
                "Recommendation summary blocked: no enabled rooms configured, action=%s score=0.00",
                RecommendationAction.NONE.value,
            )
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
            _LOGGER.debug(
                "Recommendation summary suppressed: best_room=%s action=%s score=%.2f minimum_score=%.2f "
                "reason=%s",
                best_room.room_name,
                best_room.action.value,
                weighted_score,
                self._config.minimum_score,
                "The strongest room signal is too small to notify.",
            )
            return RecommendationSummary(
                action=RecommendationAction.NONE,
                score=weighted_score,
                reason="The strongest room signal is too small to notify.",
                suggested_comfort_temperature_c=best_room.suggested_comfort_temperature_c,
                room_recommendations=room_recommendations,
                best_room=best_room.room_name,
            )
        _LOGGER.debug(
            "Recommendation summary decision: action=%s score=%.2f best_room=%s reason=%s",
            best_room.action.value,
            weighted_score,
            best_room.room_name,
            best_room.reason,
        )
        return RecommendationSummary(
            action=best_room.action,
            score=weighted_score,
            reason=best_room.reason,
            suggested_comfort_temperature_c=best_room.suggested_comfort_temperature_c,
            room_recommendations=room_recommendations,
            best_room=best_room.room_name,
        )

    def _direction_score(
        self,
        need_c: float,
        benefit_c: float,
        outdoor: ComfortObservation,
        direction: RecommendationAction,
    ) -> float:
        need_score = _smoothstep(need_c, 0.0, 4.0)
        benefit_score = _smoothstep(benefit_c, 0.4, 1.5)
        score = self._clamp(need_score * benefit_score)
        if direction == RecommendationAction.OPEN and outdoor.wind_speed_m_s is not None:
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

    def _target_reasonableness_factor(
        self,
        target_temperature_c: float,
        target_humidity_percent: float,
    ) -> float:
        temperature_distance = abs(target_temperature_c - 22.0)
        humidity_distance = abs(target_humidity_percent - 50.0)
        temperature_factor = 1.0 - _smoothstep(temperature_distance, 8.0, 20.0)
        humidity_factor = 1.0 - _smoothstep(humidity_distance, 20.0, 50.0)
        return self._clamp(min(temperature_factor, humidity_factor))

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))


def _clamp_temperature(value: float) -> float:
    return max(10.0, min(30.0, value))


def _smoothstep(value: float, edge0: float, edge1: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    x = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def _weather_requires_close(weather_condition: str | None) -> bool:
    if weather_condition is None:
        return False
    lowered = weather_condition.strip().lower()
    return any(token in lowered for token in ("thunder", "lightning", "storm", "hail"))
