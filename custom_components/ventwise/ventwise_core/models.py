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
    """Availability state for a normalized input."""

    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    STALE = "stale"
    DISABLED_BY_USER = "disabled_by_user"
    AWAITING_SOURCE = "awaiting_source"


class Validity(str, Enum):
    """Validation state for a normalized input."""

    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class Observation(Generic[T]):
    """Immutable source reading consumed by the decision engine."""

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
    """Normalized room inputs for one deterministic evaluation."""

    room_id: str
    name: str
    temperature_c: Observation[float]
    humidity_percent: Observation[float]
    window_open: Observation[bool] | None = None
    target_temperature_c: float | None = None
    target_humidity_percent: float | None = None


@dataclass(frozen=True, slots=True)
class DecisionOutdoor:
    """Normalized outdoor inputs for one deterministic evaluation."""

    temperature_c: Observation[float]
    humidity_percent: Observation[float]
    wind_speed_m_s: Observation[float] | None = None
    wind_gust_m_s: Observation[float] | None = None
    weather_condition: Observation[str] | None = None
    forecast_temperature_c: Observation[float] | None = None


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Explicit operational state; no delivery state is held by the engine."""

    quiet_hours_active: bool = False
    cooldown_active: bool = False
    stable_for_seconds: int = 0
    stability_seconds_required: int = 0


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """Complete immutable input to a deterministic decision."""

    rooms: Tuple[DecisionRoom, ...]
    outdoor: DecisionOutdoor
    evaluated_at: datetime
    context: DecisionContext = field(default_factory=DecisionContext)


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Stable, sanitized explanation entry."""

    code: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Scores for the supported action candidates."""

    open: float = 0.0
    ventilate: float = 0.0
    close: float = 0.0


@dataclass(frozen=True, slots=True)
class DataQualitySummary:
    """Deterministic inventory of accepted and rejected inputs."""

    used: Tuple[str, ...] = ()
    discarded: Tuple[str, ...] = ()
    awaiting_source: Tuple[str, ...] = ()
    diagnostics: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Core decision truth and delivery eligibility for one room."""

    room_id: str
    core_action: RecommendationAction
    delivered_action: RecommendationAction
    candidate_scores: CandidateScores
    confidence: float
    reason_code: str
    score: float = 0.0
    reason: str = ""
    target_perceived_c: float = 0.0
    indoor_perceived_c: float = 0.0
    outdoor_perceived_c: float = 0.0
    suggested_comfort_temperature_c: float = 0.0
    indoor_absolute_humidity_g_m3: float | None = None
    outdoor_absolute_humidity_g_m3: float | None = None
    moisture_delta_g_m3: float | None = None
    moisture_direction: str | None = None
    moisture_reason_code: str | None = None
    trace: Tuple[TraceEntry, ...] = ()
    data_quality: DataQualitySummary = field(default_factory=DataQualitySummary)
    delivery_suppressed_by: str | None = None


@dataclass(frozen=True, slots=True)
class AggregateDecisionResult:
    """Stable aggregate result and all per-room decisions."""

    core_action: RecommendationAction
    delivered_action: RecommendationAction
    room_results: Tuple[DecisionResult, ...] = ()
    trace: Tuple[TraceEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionConfig:
    """Versioned parameters for the minimal deterministic decision model."""

    version: str = "250-minimal-ddp-v1"
    target_temperature_c: float = 22.0
    comfort_band_c: float = 1.0
    meaningful_benefit_c: float = 0.35
    winner_margin: float = 0.05
    indoor_freshness: timedelta = timedelta(minutes=15)
    outdoor_freshness: timedelta = timedelta(minutes=15)
    temperature_min_c: float = -80.0
    temperature_max_c: float = 80.0
    humidity_min_percent: float = 0.0
    humidity_max_percent: float = 100.0
    wind_min_m_s: float = 0.0
    wind_max_m_s: float = 100.0
    wind_preference_m_s: float = 4.0
    wind_block_m_s: float = 12.0
    gust_block_m_s: float = 15.0
    minimum_moisture_delta_g_m3: float = 1.0
    moisture_rh_boundary_percent: float = 10.0
    severe_weather_tokens: Tuple[str, ...] = (
        "thunder", "lightning", "storm", "hail", "tornado", "hurricane",
        "blizzard", "squall", "freezing", "icy", "ice",
    )


class SeasonMode(str, Enum):
    """High-level season hint for optional scoring bias."""

    AUTO = "auto"
    SUMMER = "summer"
    WINTER = "winter"


@dataclass(frozen=True, slots=True)
class RoomObservation:
    """Measured conditions for a room."""

    temperature_c: float
    humidity_percent: float | None


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
    humidity_percent: float | None
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
    indoor_absolute_humidity_g_m3: float | None = None
    outdoor_absolute_humidity_g_m3: float | None = None
    moisture_delta_g_m3: float | None = None
    moisture_direction: str | None = None
    moisture_reason_code: str | None = None


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
