"""Pure deterministic decision pipeline for VentWise issue #250."""

from __future__ import annotations

from dataclasses import replace
from math import isfinite

from .models import (
    AggregateDecisionResult,
    Availability,
    CandidateScores,
    DataQualitySummary,
    DecisionConfig,
    DecisionContext,
    DecisionResult,
    DecisionRoom,
    DecisionSnapshot,
    RecommendationAction,
    TraceEntry,
    Validity,
)


def perceived_temperature(
    temperature_c: float,
    humidity_percent: float,
    target_humidity_percent: float = 50.0,
    humidity_weight: float = 0.04,
) -> float:
    """Return the stable perceived-temperature approximation used by VentWise."""

    return temperature_c + ((humidity_percent - target_humidity_percent) * humidity_weight)


def suggested_comfort_temperature(target_temperature_c: float, outdoor_perceived_c: float) -> float:
    """Return the climate-adaptive presentation target."""

    adjustment = max(-2.0, min(2.0, (outdoor_perceived_c - 20.0) * 0.25))
    return round(max(18.0, min(26.0, target_temperature_c + adjustment)), 1)


class DecisionEngine:
    """Evaluate immutable snapshots without external reads or mutable state."""

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    def evaluate(self, snapshot: DecisionSnapshot) -> AggregateDecisionResult:
        results = tuple(
            self.evaluate_room(room, snapshot)
            for room in sorted(snapshot.rooms, key=lambda item: (item.room_id, item.name))
        )
        eligible = [result for result in results if result.delivered_action is not RecommendationAction.NONE]
        candidates = eligible or list(results)
        best = min(
            candidates,
            key=lambda result: (
                -result.score,
                -result.candidate_scores.close,
                -result.candidate_scores.ventilate,
                -result.candidate_scores.open,
                result.room_id,
            ),
            default=None,
        )
        if best is None:
            return AggregateDecisionResult(RecommendationAction.NONE, RecommendationAction.NONE)
        return AggregateDecisionResult(
            core_action=best.core_action,
            delivered_action=best.delivered_action,
            room_results=results,
            trace=(TraceEntry("aggregate.selected", best.room_id),),
        )

    def evaluate_room(self, room: DecisionRoom, snapshot: DecisionSnapshot) -> DecisionResult:
        used: list[str] = []
        discarded: list[str] = []
        awaiting: list[str] = []
        trace: list[TraceEntry] = [TraceEntry("config.version", self.config.version)]

        indoor_t = self._usable(room.temperature_c, "indoor.temperature", snapshot, self.config.indoor_freshness, used, discarded, awaiting)
        indoor_h = self._usable(room.humidity_percent, "indoor.humidity", snapshot, self.config.indoor_freshness, used, discarded, awaiting)
        outdoor_t = self._usable(snapshot.outdoor.temperature_c, "outdoor.temperature", snapshot, self.config.outdoor_freshness, used, discarded, awaiting)
        outdoor_h = self._usable(snapshot.outdoor.humidity_percent, "outdoor.humidity", snapshot, self.config.outdoor_freshness, used, discarded, awaiting)
        wind = self._usable(snapshot.outdoor.wind_speed_m_s, "outdoor.wind", snapshot, self.config.outdoor_freshness, used, discarded, awaiting, optional=True)
        gust = self._usable(snapshot.outdoor.wind_gust_m_s, "outdoor.gust", snapshot, self.config.outdoor_freshness, used, discarded, awaiting, optional=True)
        weather = self._usable(snapshot.outdoor.weather_condition, "outdoor.weather", snapshot, self.config.outdoor_freshness, used, discarded, awaiting, optional=True)
        window_open = self._usable(room.window_open, "window.state", snapshot, self.config.indoor_freshness, used, discarded, awaiting, optional=True)

        quality = lambda: DataQualitySummary(tuple(used), tuple(discarded), tuple(awaiting))
        if indoor_t is None or outdoor_t is None or outdoor_h is None:
            trace.append(TraceEntry("selection.insufficient_evidence"))
            return self._result(
                room, RecommendationAction.NONE, RecommendationAction.NONE,
                CandidateScores(), 0.0, "insufficient_evidence", trace, quality(),
            )

        indoor_h_value = float(indoor_h) if indoor_h is not None else 50.0
        indoor = perceived_temperature(float(indoor_t), indoor_h_value)
        outdoor = perceived_temperature(float(outdoor_t), float(outdoor_h))
        target = room.target_temperature_c if room.target_temperature_c is not None else self.config.target_temperature_c
        target_humidity = room.target_humidity_percent if room.target_humidity_percent is not None else 50.0
        target_perceived = perceived_temperature(target, target_humidity, target_humidity)
        suggested = suggested_comfort_temperature(target, outdoor)
        inside_distance = max(0.0, abs(indoor - target_perceived) - self.config.comfort_band_c)
        outside_distance = max(0.0, abs(outdoor - target_perceived) - self.config.comfort_band_c)
        open_score = _clamp(_smoothstep(inside_distance, 0.0, 4.0) * _smoothstep(max(0.0, inside_distance - outside_distance), 0.4, 1.5))
        close_score = _clamp(_smoothstep(outside_distance, 0.0, 4.0) * _smoothstep(max(0.0, outside_distance - inside_distance), 0.4, 1.5))
        ventilate_score = 0.0
        comfort_lower = target_perceived - self.config.comfort_band_c
        comfort_upper = target_perceived + self.config.comfort_band_c
        if inside_distance <= 2.0 and (
            (indoor > comfort_upper and outdoor < comfort_lower and outdoor < indoor)
            or (indoor < comfort_lower and outdoor > comfort_upper and outdoor > indoor)
        ):
            ventilate_score = max(0.6, _clamp(_smoothstep(inside_distance, 0.0, 4.0)))
        blocks: list[str] = []
        condition = str(weather or "").strip().lower()
        severe = any(token in condition for token in self.config.severe_weather_tokens)
        effective_wind = max((value for value in (wind, gust) if value is not None), default=None)
        unsafe_wind = effective_wind is not None and effective_wind >= max(
            self.config.wind_block_m_s,
            self.config.gust_block_m_s if gust is not None and gust == effective_wind else 0.0,
        )
        if severe:
            blocks.append("severe_weather")
            trace.append(TraceEntry("block.severe_weather", condition))
        if unsafe_wind:
            blocks.append("unsafe_wind")
            trace.append(TraceEntry("block.unsafe_wind"))
        if effective_wind is not None and not unsafe_wind and effective_wind <= self.config.wind_preference_m_s:
            open_score = _clamp(open_score * (1.0 + effective_wind * 0.02))
            trace.append(TraceEntry("modifier.wind_supports_opening"))
        elif effective_wind is not None and not unsafe_wind:
            open_score = _clamp(open_score * max(0.0, 1.0 - _smoothstep(effective_wind, self.config.wind_preference_m_s, self.config.wind_block_m_s)))
            trace.append(TraceEntry("modifier.wind_reduces_opening"))

        if blocks:
            core = RecommendationAction.CLOSE
            return self._result(room, core, core, CandidateScores(close=1.0), 1.0, blocks[0], trace, quality(), target_perceived, indoor, outdoor, suggested)

        if max(inside_distance, outside_distance) < self.config.meaningful_benefit_c:
            core, reason = RecommendationAction.NONE, "insufficient_benefit"
        else:
            scores = CandidateScores(open_score, ventilate_score, close_score)
            core, reason = self._select(scores)
        scores = CandidateScores(round(open_score, 6), round(ventilate_score, 6), round(close_score, 6))
        trace.extend((TraceEntry("score.open", f"{scores.open:.6f}"), TraceEntry("score.close", f"{scores.close:.6f}"), TraceEntry(f"selection.{reason}")))
        delivered, suppressed = self._delivery(core, snapshot.context)
        if suppressed:
            trace.append(TraceEntry("delivery.suppressed", suppressed))
        return self._result(room, core, delivered, scores, max(scores.open, scores.close, scores.ventilate), reason, trace, quality(), target_perceived, indoor, outdoor, suggested, suppressed=suppressed)

    def _select(self, scores: CandidateScores) -> tuple[RecommendationAction, str]:
        ranked = sorted(((scores.open, RecommendationAction.OPEN), (scores.ventilate, RecommendationAction.VENTILATE), (scores.close, RecommendationAction.CLOSE)), key=lambda item: (-item[0], item[1].value))
        top, action = ranked[0]
        if top < self.config.meaningful_benefit_c or top - ranked[1][0] < self.config.winner_margin:
            return RecommendationAction.NONE, "insufficient_or_tied_benefit"
        return action, {RecommendationAction.OPEN: "comfort_open", RecommendationAction.VENTILATE: "comfort_ventilate", RecommendationAction.CLOSE: "comfort_close"}[action]

    @staticmethod
    def _delivery(action: RecommendationAction, context: DecisionContext) -> tuple[RecommendationAction, str | None]:
        if action is RecommendationAction.NONE:
            return action, None
        if context.quiet_hours_active:
            return RecommendationAction.NONE, "quiet_hours"
        if context.cooldown_active:
            return RecommendationAction.NONE, "cooldown"
        if context.stable_for_seconds < context.stability_seconds_required:
            return RecommendationAction.NONE, "stability"
        return action, None

    def _result(self, room, core, delivered, scores, confidence, reason, trace, quality, target=0.0, indoor=0.0, outdoor=0.0, suggested=0.0, suppressed=None):
        score = max(scores.open, scores.ventilate, scores.close)
        return DecisionResult(room.room_id, core, delivered, scores, round(confidence, 6), reason, round(score, 6), reason, target, indoor, outdoor, suggested, tuple(trace), quality, suppressed)

    @staticmethod
    def _usable(observation, name, snapshot, freshness, used, discarded, awaiting, optional=False):
        if observation is None:
            (awaiting if optional else discarded).append(name)
            return None
        if observation.availability is Availability.AWAITING_SOURCE:
            awaiting.append(name)
            return None
        if observation.availability is not Availability.AVAILABLE or observation.validity is not Validity.VALID or observation.value is None:
            discarded.append(name)
            return None
        effective_freshness = min(freshness, observation.freshness) if observation.freshness else freshness
        if observation.observed_at is None or observation.observed_at > snapshot.evaluated_at or snapshot.evaluated_at - observation.observed_at > effective_freshness:
            discarded.append(name)
            return None
        if isinstance(observation.value, float) and not isfinite(observation.value):
            discarded.append(name)
            return None
        used.append(name)
        return observation.value


def _smoothstep(value: float, edge0: float, edge1: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    x = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
