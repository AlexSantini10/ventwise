"""Compatibility facade for the deterministic decision pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .decision import DecisionEngine, perceived_temperature, suggested_comfort_temperature
from .models import (
    ComfortObservation,
    DecisionConfig,
    DecisionContext,
    DecisionOutdoor,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    RecommendationContext,
    RecommendationSummary,
    RoomProfile,
    RoomRecommendation,
    ScoringConfig,
)


class ComfortRecommender:
    """Backward-compatible adapter with no independent scoring rules."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self._config = config or ScoringConfig()
        self._engine = DecisionEngine(
            DecisionConfig(target_temperature_c=self._config.target_temperature_c)
        )

    @property
    def config(self) -> ScoringConfig:
        return self._config

    def with_config(self, config: ScoringConfig) -> "ComfortRecommender":
        return ComfortRecommender(config)

    def evaluate_room(self, room: RoomProfile, outdoor: ComfortObservation) -> RoomRecommendation:
        result = self._engine.evaluate(_snapshot((room,), outdoor, RecommendationContext())).room_results[0]
        return _to_recommendation(room, result)

    def evaluate(
        self,
        rooms: Sequence[RoomProfile],
        outdoor: ComfortObservation,
        context: RecommendationContext | None = None,
    ) -> RecommendationSummary:
        aggregate = self._engine.evaluate(_snapshot(tuple(rooms), outdoor, context or RecommendationContext()))
        profiles = {room.room_id or room.name: room for room in rooms if room.enabled}
        recommendations = tuple(_to_recommendation(profiles[item.room_id], item) for item in aggregate.room_results)
        best = next((item for item in recommendations if item.action is not RecommendationAction.NONE), recommendations[0] if recommendations else None)
        return RecommendationSummary(
            action=aggregate.delivered_action,
            score=best.score if best and aggregate.delivered_action is not RecommendationAction.NONE else 0.0,
            reason=best.reason if best else "No enabled rooms configured.",
            suggested_comfort_temperature_c=best.suggested_comfort_temperature_c if best else None,
            room_recommendations=recommendations,
            best_room=best.room_name if best else None,
        )


def _snapshot(rooms, outdoor, context) -> DecisionSnapshot:
    now = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def obs(value, unit):
        return Observation(value, unit, now, now, "compatibility")

    return DecisionSnapshot(
        rooms=tuple(
            DecisionRoom(
                room_id=room.room_id or room.name,
                name=room.name,
                temperature_c=obs(room.indoor.temperature_c, "°C"),
                humidity_percent=obs(room.indoor.humidity_percent, "%"),
                target_temperature_c=room.target_temperature_c_override if room.target_temperature_c_override_enabled else None,
                target_humidity_percent=room.target_humidity_percent_override if room.target_humidity_percent_override_enabled else None,
            )
            for room in rooms
            if room.enabled
        ),
        outdoor=DecisionOutdoor(
            temperature_c=obs(outdoor.temperature_c, "°C"),
            humidity_percent=obs(outdoor.humidity_percent, "%"),
            wind_speed_m_s=obs(outdoor.wind_speed_m_s, "m/s") if outdoor.wind_speed_m_s is not None else None,
            wind_gust_m_s=obs(outdoor.wind_gust_m_s, "m/s") if outdoor.wind_gust_m_s is not None else None,
            weather_condition=obs(outdoor.weather_condition, "") if outdoor.weather_condition is not None else None,
            forecast_temperature_c=obs(outdoor.forecast.temperature_c, "°C") if outdoor.forecast and outdoor.forecast.temperature_c is not None else None,
        ),
        evaluated_at=now,
        context=DecisionContext(
            quiet_hours_active=context.quiet_hours_active,
            cooldown_active=context.cooldown_active,
            stable_for_seconds=context.stable_for_seconds,
        ),
    )


def _to_recommendation(room: RoomProfile, result) -> RoomRecommendation:
    return RoomRecommendation(
        room_name=room.name,
        action=result.delivered_action,
        score=result.score,
        reason=result.reason,
        target_perceived_c=result.target_perceived_c,
        indoor_perceived_c=result.indoor_perceived_c,
        outdoor_perceived_c=result.outdoor_perceived_c,
        suggested_comfort_temperature_c=result.suggested_comfort_temperature_c,
        room_id=room.room_id,
        open_score=result.candidate_scores.open,
        close_score=result.candidate_scores.close,
        reason_code=result.reason_code,
        co2_ppm=room.co2_ppm,
        indoor_comfort_severity=abs(result.indoor_perceived_c - result.target_perceived_c),
        outdoor_comfort_severity=abs(result.outdoor_perceived_c - result.target_perceived_c),
    )
