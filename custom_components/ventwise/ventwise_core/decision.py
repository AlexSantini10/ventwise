"""Deterministic, source-neutral ventilation decision pipeline.

This module deliberately has no Home Assistant dependency.  Entity adapters
create :class:`DecisionSnapshot`; delivery code can then render its stable,
fully explained result without changing the physical recommendation.
"""

from __future__ import annotations

from dataclasses import replace
from math import exp, isfinite, log

from .models import (
    AggregateDecisionResult,
    Availability,
    CandidateScores,
    DataQualitySummary,
    DecisionConfig,
    DecisionResult,
    DecisionRoom,
    DecisionSnapshot,
    Observation,
    RecommendationAction,
    TraceEntry,
    Validity,
)

_SEVERE_WEATHER = (
    "thunder", "lightning", "storm", "hail", "tornado", "hurricane",
    "blizzard", "squall", "freezing", "icy", "ice",
)


def apparent_temperature_c(temperature_c: float, humidity_percent: float) -> float:
    """Return the documented warm-domain heat-index, otherwise dry bulb T."""

    if temperature_c < 26.7 or humidity_percent < 40.0:
        return temperature_c
    return (
        -8.784695 + 1.61139411 * temperature_c + 2.338549 * humidity_percent
        - 0.14611605 * temperature_c * humidity_percent
        - 0.012308094 * temperature_c**2 - 0.016424828 * humidity_percent**2
        + 0.002211732 * temperature_c**2 * humidity_percent
        + 0.00072546 * temperature_c * humidity_percent**2
        - 0.000003582 * temperature_c**2 * humidity_percent**2
    )


def dew_point_c(temperature_c: float, humidity_percent: float) -> float:
    """Return dew point with Magnus constants a=17.62 and b=243.12."""

    gamma = log(humidity_percent / 100.0) + (17.62 * temperature_c / (243.12 + temperature_c))
    return 243.12 * gamma / (17.62 - gamma)


def absolute_humidity_g_m3(temperature_c: float, humidity_percent: float) -> float:
    """Return vapour density in canonical g/m³ using the Magnus equation."""

    saturation_hpa = 6.112 * exp(17.62 * temperature_c / (243.12 + temperature_c))
    return 216.7 * (humidity_percent / 100.0) * saturation_hpa / (temperature_c + 273.15)


class DecisionEngine:
    """Apply validation, blocks, scoring, selection and delivery in order."""

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    def evaluate(self, snapshot: DecisionSnapshot) -> AggregateDecisionResult:
        """Evaluate an immutable snapshot in its supplied room order."""

        results = tuple(self.evaluate_room(room, snapshot) for room in snapshot.rooms)
        actionable = [r for r in results if r.delivered_action != RecommendationAction.NONE]
        best = max(actionable or list(results), key=lambda r: max(
            r.candidate_scores.open, r.candidate_scores.ventilate, r.candidate_scores.close
        ), default=None)
        if best is None:
            return AggregateDecisionResult(RecommendationAction.NONE, RecommendationAction.NONE, ())
        return AggregateDecisionResult(
            core_action=best.core_action,
            delivered_action=best.delivered_action,
            room_results=results,
            trace=(TraceEntry("aggregate.selected", best.room_id),),
        )

    def evaluate_room(self, room: DecisionRoom, snapshot: DecisionSnapshot) -> DecisionResult:
        """Return a deterministic room result without mutating the snapshot."""

        trace: list[TraceEntry] = [TraceEntry("config.version", self.config.version)]
        used: list[str] = []
        discarded: list[str] = []
        awaiting: list[str] = []
        blocks: list[str] = []
        penalties: list[str] = []

        indoor_t = self._usable(room.temperature_c, "indoor.temperature", snapshot, self.config.indoor_freshness, used, discarded, awaiting)
        indoor_h = self._usable(room.humidity_percent, "indoor.humidity", snapshot, self.config.indoor_freshness, used, discarded, awaiting)
        outdoor_t = self._usable(snapshot.outdoor.temperature_c, "outdoor.temperature", snapshot, self.config.weather_freshness, used, discarded, awaiting)
        outdoor_h = self._usable(snapshot.outdoor.humidity_percent, "outdoor.humidity", snapshot, self.config.weather_freshness, used, discarded, awaiting)
        weather = self._usable(snapshot.outdoor.weather_condition, "outdoor.weather", snapshot, self.config.weather_freshness, used, discarded, awaiting)
        wind = self._usable(snapshot.outdoor.wind_speed_m_s, "outdoor.wind", snapshot, self.config.weather_freshness, used, discarded, awaiting)
        gust = self._usable(snapshot.outdoor.wind_gust_m_s, "outdoor.gust", snapshot, self.config.weather_freshness, used, discarded, awaiting, optional=True)

        critical_missing = any(value is None for value in (outdoor_t, outdoor_h, weather, wind))
        if critical_missing:
            blocks.append("critical_weather_unavailable")
            trace.append(TraceEntry("block.critical_weather_unavailable"))

        known_open = self._usable(room.window_open, "window.state", snapshot, self.config.indoor_freshness, used, discarded, awaiting, optional=True)
        condition = str(weather).lower() if weather is not None else ""
        severe = any(token in condition for token in _SEVERE_WEATHER)
        hazardous_wind = (wind is not None and wind >= self.config.wind_block_m_s) or (gust is not None and gust >= self.config.gust_block_m_s)
        smoke = self._usable(snapshot.outdoor.smoke_alert, "outdoor.smoke", snapshot, self.config.weather_freshness, used, discarded, awaiting, optional=True) is True
        pollen = self._usable(snapshot.outdoor.pollen_policy, "outdoor.pollen", snapshot, self.config.weather_freshness, used, discarded, awaiting, optional=True)
        pollution = self._usable(snapshot.outdoor.pollution_policy, "outdoor.pollution", snapshot, self.config.weather_freshness, used, discarded, awaiting, optional=True)
        hard_block = severe or hazardous_wind or smoke or pollen == "avoid" or pollution == "avoid"
        if severe:
            blocks.append("severe_weather")
            trace.append(TraceEntry("block.severe_weather", condition))
        if hazardous_wind:
            blocks.append("unsafe_wind")
            trace.append(TraceEntry("block.unsafe_wind"))
        if smoke:
            blocks.append("smoke_alert")
            trace.append(TraceEntry("block.smoke_alert"))
        if pollen == "avoid" or pollution == "avoid":
            blocks.append("outdoor_exposure_avoid")
            trace.append(TraceEntry("block.outdoor_exposure_avoid"))

        if indoor_t is None or indoor_h is None:
            trace.append(TraceEntry("selection.insufficient_indoor_evidence"))
            return self._finish(room, RecommendationAction.NONE, CandidateScores(), 0.0, "insufficient_indoor_evidence", trace, blocks, penalties, used, discarded, awaiting, snapshot, known_open)
        if critical_missing or hard_block:
            close = 1.0 if known_open is True else 0.0
            core = RecommendationAction.CLOSE if close else RecommendationAction.NONE
            code = blocks[0] if blocks else "critical_weather_unavailable"
            return self._finish(room, core, CandidateScores(close=close), 1.0 if hard_block else 0.4, code, trace, blocks, penalties, used, discarded, awaiting, snapshot, known_open, urgent=hard_block)

        assert outdoor_t is not None and outdoor_h is not None
        indoor_apparent = apparent_temperature_c(float(indoor_t), float(indoor_h))
        outdoor_apparent = apparent_temperature_c(float(outdoor_t), float(outdoor_h))
        target = room.target_temperature_c if room.target_temperature_c is not None else self.config.target_temperature_c
        indoor_distance = max(0.0, abs(indoor_apparent - target) - self.config.comfort_band_c)
        outdoor_distance = max(0.0, abs(outdoor_apparent - target) - self.config.comfort_band_c)
        thermal_benefit = max(0.0, indoor_distance - outdoor_distance)
        indoor_ah = absolute_humidity_g_m3(float(indoor_t), float(indoor_h))
        outdoor_ah = absolute_humidity_g_m3(float(outdoor_t), float(outdoor_h))
        moisture_benefit = max(0.0, indoor_ah - outdoor_ah)
        co2 = self._usable(room.co2_ppm, "indoor.co2", snapshot, self.config.indoor_freshness, used, discarded, awaiting, optional=True)
        co2_trend = self._usable(room.co2_trend_ppm_per_hour, "indoor.co2_trend", snapshot, self.config.indoor_freshness, used, discarded, awaiting, optional=True)
        co2_signal = (co2 is not None and co2 >= self.config.co2_threshold_ppm) or (co2_trend is not None and co2_trend >= self.config.co2_positive_trend_ppm_per_hour)

        # A stable endpoint may sit just outside the preferred band without
        # being a transient-only correction.  The meaningful-benefit setting
        # is the documented tolerance for that practical boundary.
        open_score = thermal_benefit if outdoor_distance <= self.config.meaningful_benefit else 0.0
        transient = thermal_benefit if outdoor_distance > self.config.meaningful_benefit else 0.0
        # Vapour exchange is a targeted signal only when the room is actually
        # above its humidity preference.  A warmer room naturally has higher
        # absolute humidity at the same RH; treating that alone as a competing
        # ventilation signal would incorrectly defeat a sustained thermal open.
        moisture_signal = moisture_benefit if float(indoor_h) > self.config.humidity_high_percent else 0.0
        ventilate_score = max(transient, moisture_signal, self.config.meaningful_benefit if co2_signal else 0.0)
        close_score = max(0.0, outdoor_distance - indoor_distance)
        if pollen == "reduce" or pollution == "reduce":
            open_score = max(0.0, open_score - self.config.meaningful_benefit)
            ventilate_score = max(0.0, ventilate_score - self.config.meaningful_benefit)
            penalties.append("outdoor_exposure_reduce")
            trace.append(TraceEntry("penalty.outdoor_exposure_reduce"))
        forecast = self._usable(snapshot.outdoor.forecast_temperature_c, "forecast.temperature", snapshot, self.config.forecast_freshness, used, discarded, awaiting, optional=True)
        rain = self._usable(snapshot.outdoor.precipitation_probability_percent, "forecast.rain", snapshot, self.config.forecast_freshness, used, discarded, awaiting, optional=True)
        if rain is not None and rain >= self.config.imminent_rain_probability_percent:
            open_score = 0.0
            ventilate_score = max(0.0, ventilate_score - self.config.meaningful_benefit)
            penalties.append("imminent_rain")
            trace.append(TraceEntry("penalty.imminent_rain"))
        scores = CandidateScores(round(open_score, 6), round(ventilate_score, 6), round(close_score, 6))
        core, reason = self._select(scores)
        duration = self._duration(core, forecast, rain)
        trace.extend((TraceEntry("score.thermal", f"{thermal_benefit:.3f}"), TraceEntry("score.moisture", f"{moisture_benefit:.3f}"), TraceEntry("selection." + reason)))
        confidence = 1.0 if not discarded else max(0.3, 1.0 - 0.1 * len(discarded))
        return self._finish(room, core, scores, confidence, reason, trace, blocks, penalties, used, discarded, awaiting, snapshot, known_open, duration)

    def _usable(self, observation: Observation | None, name: str, snapshot: DecisionSnapshot, limit, used, discarded, awaiting, optional: bool = False):
        if observation is None:
            (discarded if not optional else awaiting).append(name)
            return None
        if observation.availability == Availability.AWAITING_SOURCE:
            awaiting.append(name)
            return None
        if observation.availability != Availability.AVAILABLE or observation.validity != Validity.VALID or observation.value is None:
            discarded.append(name)
            return None
        effective_limit = min(limit, observation.freshness) if observation.freshness is not None else limit
        if observation.observed_at is None or snapshot.evaluated_at - observation.observed_at > effective_limit:
            discarded.append(name)
            return None
        value = observation.value
        if isinstance(value, float) and (not isfinite(value) or not self._plausible(name, value)):
            discarded.append(name)
            return None
        used.append(name)
        return value

    @staticmethod
    def _plausible(name: str, value: float) -> bool:
        if "humidity" in name or "rain" in name:
            return 0.0 <= value <= 100.0
        if "temperature" in name:
            return -90.0 <= value <= 70.0
        return value >= 0.0

    def _select(self, scores: CandidateScores) -> tuple[RecommendationAction, str]:
        ranked = sorted(((scores.open, RecommendationAction.OPEN), (scores.ventilate, RecommendationAction.VENTILATE), (scores.close, RecommendationAction.CLOSE)), reverse=True, key=lambda item: item[0])
        top, action = ranked[0]
        if top < self.config.meaningful_benefit or top - ranked[1][0] < self.config.winner_margin:
            return RecommendationAction.NONE, "insufficient_or_tied_benefit"
        return action, {RecommendationAction.OPEN: "thermal_sustained_benefit", RecommendationAction.VENTILATE: "targeted_ventilation_benefit", RecommendationAction.CLOSE: "outdoor_materially_worse"}[action]

    @staticmethod
    def _duration(action: RecommendationAction, forecast, rain) -> int | None:
        if action != RecommendationAction.VENTILATE:
            return None
        return 5 if rain is not None and rain >= 60.0 else (10 if forecast is not None else 15)

    def _finish(self, room, core, scores, confidence, reason, trace, blocks, penalties, used, discarded, awaiting, snapshot, known_open, duration=None, urgent=False):
        delivered, suppressed = core, None
        if core != RecommendationAction.NONE and known_open is not None:
            if known_open and core in (RecommendationAction.OPEN, RecommendationAction.VENTILATE):
                delivered, suppressed = RecommendationAction.NONE, "window_already_open"
            elif not known_open and core == RecommendationAction.CLOSE:
                delivered, suppressed = RecommendationAction.NONE, "window_already_closed"
        if not urgent and delivered != RecommendationAction.NONE:
            context = snapshot.operational
            if context.quiet_hours_active:
                delivered, suppressed = RecommendationAction.NONE, "quiet_hours"
            elif context.cooldown_active:
                delivered, suppressed = RecommendationAction.NONE, "cooldown"
            elif context.stable_for_seconds < 0:
                delivered, suppressed = RecommendationAction.NONE, "stability"
        if suppressed:
            trace.append(TraceEntry("delivery.suppressed", suppressed))
        return DecisionResult(room.room_id, core, delivered, duration, scores, round(confidence, 6), reason, tuple(trace), tuple(blocks), tuple(penalties), DataQualitySummary(tuple(used), tuple(discarded), tuple(awaiting)), suppressed)
