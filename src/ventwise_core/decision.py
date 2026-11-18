"""Pure, deterministic VentWise decision pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .models import (
    AggregateDecisionResult,
    Availability,
    CandidateScores,
    DataQualitySummary,
    DecisionResult,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    TraceEntry,
    Validity,
)
from .psychrometrics import absolute_humidity_g_m3, perceived_temperature_c, pressure_hpa_or_default


@dataclass(frozen=True, slots=True)
class DecisionConfig:
    """Versioned parameters for the first active DDP."""

    version: str = "ddp-v0.18"
    target_temperature_c: float = 22.0
    comfort_band_c: float = 1.0
    meaningful_benefit: float = 0.35
    winner_margin: float = 0.05
    freshness_seconds: int = 900
    wind_preference_m_s: float = 4.0
    wind_block_m_s: float = 12.0
    gust_block_m_s: float = 15.0
    co2_enabled: bool = False
    co2_threshold_ppm: float = 1000.0
    co2_weight: float = 0.35


class DecisionEngine:
    """Evaluate canonical snapshots without I/O, wall-clock reads, or mutation."""

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    def evaluate(self, snapshot: DecisionSnapshot) -> AggregateDecisionResult:
        results = tuple(
            self.evaluate_room(room, snapshot)
            for room in sorted(snapshot.rooms, key=lambda item: (item.room_id, item.name))
        )
        actionable = [
            result for result in results
            if result.delivered_action is not RecommendationAction.NONE
        ]
        candidates = actionable or list(results)
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
            evaluated_at=snapshot.evaluated_at,
        )

    def evaluate_room(self, room: DecisionRoom, snapshot: DecisionSnapshot) -> DecisionResult:
        used: list[str] = []
        discarded: list[str] = []
        discarded_reasons: list[str] = []
        awaiting: list[str] = []
        trace: list[TraceEntry] = [TraceEntry("config.version", self.config.version)]

        indoor_t = self._usable(room.temperature_c, "indoor.temperature", snapshot, used, discarded, awaiting, discarded_reasons)
        outdoor_t = self._usable(snapshot.outdoor.temperature_c, "outdoor.temperature", snapshot, used, discarded, awaiting, discarded_reasons)
        outdoor_h = self._usable(snapshot.outdoor.humidity_percent, "outdoor.humidity", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        pressure = self._usable(snapshot.outdoor.pressure_hpa, "outdoor.pressure", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        indoor_h = self._usable(room.humidity_percent, "indoor.humidity", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        wind = self._usable(snapshot.outdoor.wind_speed_m_s, "outdoor.wind", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        gust = self._usable(snapshot.outdoor.wind_gust_m_s, "outdoor.gust", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        weather = self._usable(snapshot.outdoor.weather_condition, "outdoor.weather", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        co2 = self._usable(room.co2_ppm, "indoor.co2", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)
        contact = self._usable(room.window_open, "room.window_contact", snapshot, used, discarded, awaiting, discarded_reasons, optional=True)

        quality = DataQualitySummary(tuple(used), tuple(discarded), tuple(awaiting), tuple(discarded_reasons))
        if indoor_t is None or outdoor_t is None:
            trace.append(TraceEntry("selection.insufficient_evidence"))
            return self._result(room, RecommendationAction.NONE, RecommendationAction.NONE, CandidateScores(), 0.0, "insufficient_evidence", trace, quality, evaluated_at=snapshot.evaluated_at)
        safety_quality = any(
            entry.startswith(("outdoor.wind:", "outdoor.gust:", "outdoor.weather:"))
            for entry in discarded_reasons
        )
        if safety_quality or (
            snapshot.outdoor.safety_evidence_configured
            and not any(name in used for name in ("outdoor.wind", "outdoor.gust", "outdoor.weather"))
        ):
            trace.append(TraceEntry("selection.safety_uncertain"))
            return self._result(room, RecommendationAction.NONE, RecommendationAction.NONE, CandidateScores(), 0.0, "safety_uncertain", trace, quality, evaluated_at=snapshot.evaluated_at)
        if room.window_contact_configured and contact is None:
            # A contact failure must not hide an independent safety close.
            # Ordinary opening/ventilation remains blocked below.
            contact_uncertain = True
        else:
            contact_uncertain = False

        baseline = _baseline(room)
        trace.append(TraceEntry("baseline.selected", baseline))
        for name, observation in sorted(
            (("indoor.temperature", room.temperature_c), ("indoor.humidity", room.humidity_percent),
             ("indoor.co2", room.co2_ppm), ("outdoor.temperature", snapshot.outdoor.temperature_c),
             ("outdoor.humidity", snapshot.outdoor.humidity_percent), ("outdoor.pressure", snapshot.outdoor.pressure_hpa)),
            key=lambda item: item[0],
        ):
            if observation is not None and observation.source_id:
                trace.append(TraceEntry(f"provenance.{name}", observation.source_id))

        indoor_h_value = float(indoor_h) if indoor_h is not None else None
        outdoor_h_value = float(outdoor_h) if outdoor_h is not None else None
        co2_value = float(co2) if co2 is not None else None
        target = room.target_temperature_c if room.target_temperature_c is not None else self.config.target_temperature_c
        target_humidity = room.target_humidity_percent if room.target_humidity_percent is not None else 50.0
        indoor = perceived_temperature_c(float(indoor_t), indoor_h_value, target, target_humidity)
        outdoor = perceived_temperature_c(float(outdoor_t), outdoor_h_value, target, target_humidity)
        target_perceived = perceived_temperature_c(target, target_humidity, target, target_humidity)
        suggested = _suggested_temperature(target, outdoor)
        inside_distance = max(0.0, abs(indoor - target_perceived) - self.config.comfort_band_c)
        outside_distance = max(0.0, abs(outdoor - target_perceived) - self.config.comfort_band_c)
        trace.append(TraceEntry("component.temperature", f"{max(inside_distance, outside_distance):.6f}"))
        if indoor_h_value is not None and outdoor_h_value is not None:
            trace.append(TraceEntry("component.humidity", f"{abs(outdoor_h_value - indoor_h_value):.6f}"))
        open_score = _clamp(_smoothstep(inside_distance, 0.0, 4.0) * _smoothstep(max(0.0, inside_distance - outside_distance), 0.4, 1.5))
        close_score = _clamp(_smoothstep(outside_distance, 0.0, 4.0) * _smoothstep(max(0.0, outside_distance - inside_distance), 0.4, 1.5))
        ventilate_score = 0.0
        if inside_distance <= 2.0 and (
            (indoor > target_perceived + self.config.comfort_band_c and outdoor < target_perceived - self.config.comfort_band_c)
            or (indoor < target_perceived - self.config.comfort_band_c and outdoor > target_perceived + self.config.comfort_band_c)
        ):
            ventilate_score = max(0.6, _smoothstep(inside_distance, 0.0, 4.0))

        pressure_hpa, pressure_estimated = pressure_hpa_or_default(float(pressure) if pressure is not None else None)
        if pressure_estimated:
            trace.append(TraceEntry("quality.pressure", "estimated:1013.25"))
        moisture_delta = None
        if indoor_h_value is not None and outdoor_h_value is not None:
            indoor_absolute = absolute_humidity_g_m3(float(indoor_t), indoor_h_value)
            outdoor_absolute = absolute_humidity_g_m3(float(outdoor_t), outdoor_h_value)
            moisture_delta = outdoor_absolute - indoor_absolute
            moisture_benefit = _clamp(abs(moisture_delta) / 4.0)
            trace.append(TraceEntry("component.absolute_humidity", f"{moisture_delta:.6f}"))
            if (inside_distance > 0.0 and abs(moisture_delta) > 0.1):
                open_score = _clamp(open_score + moisture_benefit * 0.2)
                ventilate_score = max(ventilate_score, moisture_benefit * 0.75)
                trace.append(TraceEntry("objective.moisture_exchange", "drying" if moisture_delta < -0.1 else "humidifying"))

        co2_influence = 0.0
        if self.config.co2_enabled and co2_value is not None:
            co2_influence = _clamp((co2_value - self.config.co2_threshold_ppm) / max(self.config.co2_threshold_ppm, 1.0))
            if co2_influence > 0.0:
                ventilate_score = _clamp(max(
                    ventilate_score + co2_influence * self.config.co2_weight,
                    self.config.meaningful_benefit + co2_influence * (1.0 - self.config.meaningful_benefit),
                ))
                trace.append(TraceEntry("objective.co2", f"{co2_influence:.6f}"))

        effective_wind = max((float(value) for value in (wind, gust) if value is not None), default=None)
        severe = any(token in str(weather or "").lower() for token in ("thunder", "lightning", "storm", "hail", "tornado", "hurricane", "blizzard"))
        unsafe_wind = effective_wind is not None and effective_wind >= max(
            self.config.wind_block_m_s,
            self.config.gust_block_m_s if gust is not None and gust == effective_wind else 0.0,
        )
        contact_open = contact is True
        if severe or unsafe_wind:
            code = "severe_weather" if severe else "unsafe_wind"
            trace.append(TraceEntry(f"block.{code}"))
            return self._result(room, RecommendationAction.CLOSE, RecommendationAction.CLOSE, CandidateScores(close=1.0), 1.0, code, trace, quality, target_perceived, indoor, outdoor, suggested, evaluated_at=snapshot.evaluated_at, urgent=contact_open)

        if contact_uncertain:
            trace.append(TraceEntry("selection.contact_uncertain"))
            return self._result(room, RecommendationAction.NONE, RecommendationAction.NONE, CandidateScores(), 0.0, "contact_uncertain", trace, quality, target_perceived, indoor, outdoor, suggested, evaluated_at=snapshot.evaluated_at)

        if effective_wind is not None and effective_wind <= self.config.wind_preference_m_s:
            open_score = _clamp(open_score * (1.0 + effective_wind * 0.02))
            trace.append(TraceEntry("modifier.wind_supports_opening"))
        elif effective_wind is not None:
            open_score = _clamp(open_score * (1.0 - _smoothstep(effective_wind, self.config.wind_preference_m_s, self.config.wind_block_m_s)))
            trace.append(TraceEntry("modifier.wind_reduces_opening"))

        penalties = (TraceEntry("penalty.wind", f"{max(0.0, 1.0 - open_score):.6f}"),) if effective_wind is not None else ()
        scores = CandidateScores(round(open_score, 6), round(ventilate_score, 6), round(close_score, 6), penalties=penalties)
        co2_trigger = self.config.co2_enabled and co2_value is not None and co2_value >= self.config.co2_threshold_ppm
        if co2_trigger:
            action, reason = RecommendationAction.VENTILATE, "co2_ventilation"
        elif max(inside_distance, outside_distance, co2_influence) < self.config.meaningful_benefit:
            action, reason = RecommendationAction.NONE, "insufficient_benefit"
        else:
            action, reason = self._select(scores)
        trace.extend((TraceEntry("score.open", f"{scores.open:.6f}"), TraceEntry("score.ventilate", f"{scores.ventilate:.6f}"), TraceEntry("score.close", f"{scores.close:.6f}"), TraceEntry("score.none", "0.000000"), TraceEntry(f"selection.{reason}")))
        delivered, suppressed = self._delivery(action, snapshot)
        if suppressed:
            trace.append(TraceEntry("delivery.suppressed", suppressed))
        confidence = max(scores.open, scores.ventilate, scores.close) * (0.8 if pressure_estimated else 1.0)
        return self._result(room, action, delivered, scores, confidence, reason, trace, quality, target_perceived, indoor, outdoor, suggested, suppressed, co2_value, co2_influence, evaluated_at=snapshot.evaluated_at, baseline=baseline)

    def _select(self, scores: CandidateScores) -> tuple[RecommendationAction, str]:
        ranked = sorted(((scores.open, RecommendationAction.OPEN), (scores.ventilate, RecommendationAction.VENTILATE), (scores.close, RecommendationAction.CLOSE)), key=lambda item: (-item[0], item[1].value))
        top, action = ranked[0]
        if top < self.config.meaningful_benefit or top - ranked[1][0] < self.config.winner_margin:
            return RecommendationAction.NONE, "insufficient_or_tied_benefit"
        return action, {RecommendationAction.OPEN: "comfort_open", RecommendationAction.VENTILATE: "comfort_ventilate", RecommendationAction.CLOSE: "comfort_close"}[action]

    @staticmethod
    def _delivery(action: RecommendationAction, snapshot: DecisionSnapshot) -> tuple[RecommendationAction, str | None]:
        context = snapshot.context
        if action is RecommendationAction.NONE:
            return action, None
        if action is RecommendationAction.CLOSE:
            return action, None
        if context.quiet_hours_active:
            return RecommendationAction.NONE, "quiet_hours"
        if context.cooldown_active:
            return RecommendationAction.NONE, "cooldown"
        if context.stable_for_seconds < context.stability_seconds_required:
            return RecommendationAction.NONE, "stability"
        return action, None

    def _usable(self, observation: Observation | None, name: str, snapshot: DecisionSnapshot, used: list[str], discarded: list[str], awaiting: list[str], discarded_reasons: list[str], optional: bool = False):
        if observation is None:
            (awaiting if optional else discarded).append(name)
            if not optional:
                discarded_reasons.append(f"{name}:missing")
            return None
        if observation.availability in {Availability.AWAITING_SOURCE, Availability.UNCONFIGURED}:
            awaiting.append(name)
            return None
        if observation.availability not in {Availability.AVAILABLE, Availability.ESTIMATED} or observation.validity is not Validity.VALID or observation.value is None:
            if optional and observation.availability is Availability.MISSING:
                awaiting.append(name)
            else:
                discarded.append(name)
                discarded_reasons.append(f"{name}:{observation.quality_reason or observation.availability.value}")
            return None
        if observation.observed_at is None:
            discarded.append(name)
            discarded_reasons.append(f"{name}:missing_timestamp")
            return None
        observed_at = _comparable_datetime(observation.observed_at, snapshot.evaluated_at)
        evaluated_at = _comparable_datetime(snapshot.evaluated_at, observation.observed_at)
        if observed_at > evaluated_at:
            discarded.append(name)
            discarded_reasons.append(f"{name}:future_timestamp")
            return None
        age = evaluated_at - observed_at
        freshness = observation.freshness
        too_old = age > freshness if freshness is not None else age.total_seconds() > self.config.freshness_seconds
        if too_old:
            discarded.append(name)
            discarded_reasons.append(f"{name}:stale")
            return None
        if isinstance(observation.value, float) and not isfinite(observation.value):
            discarded.append(name)
            discarded_reasons.append(f"{name}:non_finite")
            return None
        if not _plausible(observation.value, observation.unit):
            discarded.append(name)
            discarded_reasons.append(f"{name}:out_of_range")
            return None
        used.append(name)
        return observation.value

    @staticmethod
    def _result(room: DecisionRoom, core: RecommendationAction, delivered: RecommendationAction, scores: CandidateScores, confidence: float, reason: str, trace: list[TraceEntry], quality: DataQualitySummary, target: float = 0.0, indoor: float = 0.0, outdoor: float = 0.0, suggested: float = 0.0, suppressed: str | None = None, co2: float | None = None, co2_influence: float = 0.0, *, evaluated_at=None, urgent: bool = False, baseline: str = "UNKNOWN") -> DecisionResult:
        quality_state = Availability.ESTIMATED if any(entry.code == "quality.pressure" for entry in trace) else Availability.AVAILABLE
        return DecisionResult(room.room_id, core, delivered, scores, round(confidence, 6), reason, round(max(scores.open, scores.ventilate, scores.close), 6), reason, target, indoor, outdoor, suggested, tuple(trace), quality, suppressed, evaluated_at=evaluated_at, baseline=baseline, component_contributions=tuple(entry for entry in trace if entry.code.startswith(("objective.", "penalty.", "component."))), urgent=urgent, co2_ppm=co2, co2_influence=round(co2_influence, 6), quality=quality_state)


def _baseline(room: DecisionRoom) -> str:
    """Return the state maintained when no candidate is selected."""

    if room.window_open is not None and room.window_open.availability in {Availability.AVAILABLE, Availability.ESTIMATED}:
        if room.window_open.value is True:
            return "KEEP_OPEN"
        if room.window_open.value is False:
            return "KEEP_CLOSED"
    return "KEEP_CLOSED" if not room.window_contact_configured else "UNKNOWN"


def _suggested_temperature(target: float, outdoor: float) -> float:
    return round(max(18.0, min(26.0, target + max(-2.0, min(2.0, (outdoor - 20.0) * 0.25)))), 1)


def _smoothstep(value: float, edge0: float, edge1: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    x = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _plausible(value: object, unit: str) -> bool:
    """Reject physically impossible canonical boundary values."""

    if not isinstance(value, (int, float)):
        return True
    if unit == "%":
        return 0.0 <= float(value) <= 100.0
    if unit in {"Â°C", "C"}:
        return -90.0 <= float(value) <= 70.0
    if unit == "m/s":
        return 0.0 <= float(value) <= 150.0
    return True


def _comparable_datetime(value, reference):
    """Make naive legacy timestamps comparable without changing their meaning."""
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


