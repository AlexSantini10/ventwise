"""Core data models for VentWise recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Generic, Tuple, TypeVar


T = TypeVar("T")


class RecommendationAction(str, Enum):
    """Action that the recommender can return."""

    OPEN = "open"
    VENTILATE = "ventilate"
    CLOSE = "close"
    NONE = "none"


class Availability(str, Enum):
    """Whether an input may be used by a deterministic decision."""

    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    STALE = "stale"
    DISABLED_BY_USER = "disabled_by_user"
    AWAITING_SOURCE = "awaiting_source"


class Validity(str, Enum):
    """Validation state reported by an adapter."""

    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class Observation(Generic[T]):
    """Source-neutral reading retained with provenance and quality.

    Adapters must never turn an absent future source into a guessed value.  A
    value is usable only when both ``availability`` and ``validity`` say so;
    the engine independently applies its freshness limits using
    ``observed_at``.
    """

    value: T | None
    unit: str
    observed_at: datetime | None
    received_at: datetime | None
    source_id: str | None
    validity: Validity = Validity.VALID
    freshness: timedelta | None = None
    availability: Availability = Availability.AVAILABLE


@dataclass(frozen=True, slots=True)
class DecisionRoom:
    """All source-neutral room readings used by the new decision engine."""

    room_id: str
    name: str
    temperature_c: Observation[float]
    humidity_percent: Observation[float]
    co2_ppm: Observation[float] | None = None
    co2_trend_ppm_per_hour: Observation[float] | None = None
    window_open: Observation[bool] | None = None
    target_temperature_c: float | None = None
    target_humidity_percent: float | None = None


@dataclass(frozen=True, slots=True)
class DecisionOutdoor:
    """Outdoor observations; optional sources remain explicitly optional."""

    temperature_c: Observation[float]
    humidity_percent: Observation[float]
    wind_speed_m_s: Observation[float] | None = None
    wind_gust_m_s: Observation[float] | None = None
    weather_condition: Observation[str] | None = None
    precipitation_probability_percent: Observation[float] | None = None
    forecast_temperature_c: Observation[float] | None = None
    smoke_alert: Observation[bool] | None = None
    pollen_policy: Observation[str] | None = None
    pollution_policy: Observation[str] | None = None
    exposure: Tuple["ExposureReading", ...] = ()


@dataclass(frozen=True, slots=True)
class ExposureReading:
    """One pollutant or pollen reading with policy-critical metadata."""

    kind: str
    observation: Observation[float]
    averaging_period: str = "instant"
    attribution: str | None = None
    resolution: str | None = None
    coverage: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """Immutable, adapter-ready input to the deterministic engine."""

    rooms: Tuple[DecisionRoom, ...]
    outdoor: DecisionOutdoor
    evaluated_at: datetime
    operational: "RecommendationContext" = field(default_factory=lambda: RecommendationContext())


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Stable, ordered explanation entry suitable for UI, logs and tests."""

    code: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Candidate action scores before the winner-margin selection."""

    open: float = 0.0
    ventilate: float = 0.0
    close: float = 0.0


@dataclass(frozen=True, slots=True)
class DataQualitySummary:
    """Deterministic inventory of used and unavailable inputs."""

    used: Tuple[str, ...] = ()
    discarded: Tuple[str, ...] = ()
    awaiting_source: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Core truth and independently delivered action for one room."""

    room_id: str
    core_action: RecommendationAction
    delivered_action: RecommendationAction
    duration_minutes: int | None
    candidate_scores: CandidateScores
    confidence: float
    reason_code: str
    trace: Tuple[TraceEntry, ...] = ()
    blocked_conditions: Tuple[str, ...] = ()
    applied_penalties: Tuple[str, ...] = ()
    data_quality: DataQualitySummary = field(default_factory=DataQualitySummary)
    delivery_suppressed_by: str | None = None


@dataclass(frozen=True, slots=True)
class AggregateDecisionResult:
    """Per-room deterministic output and its highest-priority delivery result."""

    core_action: RecommendationAction
    delivered_action: RecommendationAction
    room_results: Tuple[DecisionResult, ...]
    trace: Tuple[TraceEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionConfig:
    """Versioned physical and safety parameters for ``DecisionEngine``."""

    version: str = "2026-11-09"
    target_temperature_c: float = 22.0
    comfort_band_c: float = 1.0
    humidity_low_percent: float = 40.0
    humidity_high_percent: float = 60.0
    meaningful_benefit: float = 1.0
    winner_margin: float = 0.05
    co2_threshold_ppm: float = 1000.0
    co2_positive_trend_ppm_per_hour: float = 150.0
    wind_block_m_s: float = 35.0 / 3.6
    gust_block_m_s: float = 50.0 / 3.6
    imminent_rain_probability_percent: float = 60.0
    indoor_freshness: timedelta = timedelta(minutes=15)
    weather_freshness: timedelta = timedelta(minutes=15)
    forecast_freshness: timedelta = timedelta(minutes=90)


class SeasonMode(str, Enum):
    """High-level season hint for optional scoring bias."""

    AUTO = "auto"
    SUMMER = "summer"
    WINTER = "winter"


@dataclass(frozen=True, slots=True)
class RoomObservation:
    """Measured conditions for a room."""

    temperature_c: float
    humidity_percent: float


@dataclass(frozen=True, slots=True)
class RoomProfile:
    """Static room metadata used by the scoring engine."""

    name: str
    indoor: RoomObservation
    kind: str = "room"
    room_id: str | None = None
    enabled: bool = True
    target_temperature_c_override_enabled: bool = False
    target_temperature_c_override: float | None = None
    target_humidity_percent_override_enabled: bool = False
    target_humidity_percent_override: float | None = None
    co2_ppm: float | None = None


@dataclass(frozen=True, slots=True)
class ForecastObservation:
    """A near-term outdoor forecast used to avoid imminent deterioration."""

    temperature_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_m_s: float | None = None
    wind_gust_m_s: float | None = None
    weather_condition: str | None = None
    precipitation_probability: float | None = None


@dataclass(frozen=True, slots=True)
class ComfortObservation:
    """Outdoor or target comfort context."""

    temperature_c: float
    humidity_percent: float
    wind_speed_m_s: float | None = None
    wind_gust_m_s: float | None = None
    weather_condition: str | None = None
    forecast_temperature_c: float | None = None
    forecast: ForecastObservation | None = None


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Tunable scoring parameters."""

    target_temperature_c: float = 22.0
    target_humidity_percent: float = 50.0
    soft_outdoor_threshold_c: float = 22.0
    minimum_score: float = 0.35
    minimum_stability_seconds: int = 0
    decision_threshold_c: float = 1.0
    score_scale_c: float = 1.8
    humidity_weight: float = 0.04
    wind_open_preference_threshold_m_s: float = 4.0
    wind_open_preference_per_m_s: float = 0.02
    wind_open_penalty_per_m_s: float = 0.07
    wind_open_block_m_s: float = 12.0
    wind_gust_open_block_m_s: float = 15.0
    weather_open_block_conditions: Tuple[str, ...] = (
        "thunder",
        "lightning",
        "storm",
        "hail",
        "tornado",
        "hurricane",
        "blizzard",
        "squall",
        "freezing",
        "icy",
        "ice",
    )
    weather_open_reduce_conditions: Tuple[str, ...] = (
        "rain",
        "drizzle",
        "shower",
        "snow",
        "sleet",
        "fog",
        "mist",
        "haze",
        "smoke",
        "windy",
        "gust",
    )
    soft_threshold_penalty: float = 0.7
    season_mode: SeasonMode = SeasonMode.AUTO
    open_bias: float = 0.0
    close_bias: float = 0.0
    co2_enabled: bool = False
    co2_threshold_ppm: float = 1000.0


@dataclass(frozen=True, slots=True)
class RecommendationContext:
    """Gating information for notification control."""

    quiet_hours_active: bool = False
    cooldown_active: bool = False
    stable_for_seconds: int = 0
    stability_seconds_required: int = 0


@dataclass(frozen=True, slots=True)
class RoomRecommendation:
    """Recommendation for a single room."""

    room_name: str
    action: RecommendationAction
    score: float
    reason: str
    target_perceived_c: float
    indoor_perceived_c: float
    outdoor_perceived_c: float
    suggested_comfort_temperature_c: float
    room_id: str | None = None
    open_score: float = 0.0
    close_score: float = 0.0
    reason_code: str = "comfort"
    co2_ppm: float | None = None
    co2_influence: float = 0.0
    ventilation_duration_minutes: int | None = None
    indoor_comfort_severity: float = 0.0
    outdoor_comfort_severity: float = 0.0


@dataclass(frozen=True, slots=True)
class RecommendationSummary:
    """Result returned by the core engine."""

    action: RecommendationAction
    score: float
    reason: str
    suggested_comfort_temperature_c: float | None = None
    room_recommendations: Tuple[RoomRecommendation, ...] = field(default_factory=tuple)
    blocked_by: str | None = None
    best_room: str | None = None
