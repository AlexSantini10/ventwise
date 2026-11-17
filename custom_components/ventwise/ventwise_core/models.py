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


class SeasonMode(str, Enum):
    """High-level season hint for optional scoring bias."""

    AUTO = "auto"
    SUMMER = "summer"
    WINTER = "winter"


@dataclass(frozen=True, slots=True)
class SourceReading:
    """Un-normalized boundary reading retained until snapshot construction."""

    value: object
    unit: str | None
    observed_at: datetime | None
    source_id: str | None
    device_class: str | None = None


@dataclass(frozen=True, slots=True)
class RoomObservation:
    """Measured conditions for a room."""

    temperature_c: float
    humidity_percent: float | None
    temperature_source: SourceReading | None = None
    humidity_source: SourceReading | None = None
    co2_ppm: float | None = None
    co2_source: SourceReading | None = None


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
    co2_source: SourceReading | None = None


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
    temperature_source: SourceReading | None = None
    humidity_source: SourceReading | None = None
    wind_speed_source: SourceReading | None = None
    wind_gust_source: SourceReading | None = None
    safety_evidence_configured: bool = False


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


class Availability(str, Enum):
    """Availability state for a normalized observation."""

    AVAILABLE = "available"
    # Public quality vocabulary; AVAILABLE remains the backwards-compatible name.
    VALID = "available"
    MISSING = "missing"
    INVALID = "invalid"
    STALE = "stale"
    UNCONFIGURED = "unconfigured"
    ESTIMATED = "estimated"
    AWAITING_SOURCE = "awaiting_source"


class Validity(str, Enum):
    """Validation state for a normalized observation."""

    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class Observation(Generic[T]):
    """Immutable, timestamped value consumed by the decision engine."""

    value: T | None
    unit: str
    observed_at: datetime | None
    source_id: str | None
    validity: Validity = Validity.VALID
    availability: Availability = Availability.AVAILABLE
    freshness: timedelta | None = None
    quality_reason: str | None = None
    provenance: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionRoom:
    """Canonical inputs for one room evaluation."""

    room_id: str
    name: str
    temperature_c: Observation[float]
    humidity_percent: Observation[float] | None
    window_open: Observation[bool] | None = None
    target_temperature_c: float | None = None
    target_humidity_percent: float | None = None
    co2_ppm: Observation[float] | None = None
    window_contact_configured: bool = False


@dataclass(frozen=True, slots=True)
class DecisionOutdoor:
    """Canonical outdoor inputs for one evaluation."""

    temperature_c: Observation[float]
    humidity_percent: Observation[float] | None
    wind_speed_m_s: Observation[float] | None = None
    wind_gust_m_s: Observation[float] | None = None
    weather_condition: Observation[str] | None = None
    safety_evidence_configured: bool = False
    pressure_hpa: Observation[float] | None = None


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Explicit delivery context; the core does not own notification state."""

    quiet_hours_active: bool = False
    cooldown_active: bool = False
    stable_for_seconds: int = 0
    stability_seconds_required: int = 0


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """Complete immutable input to a deterministic evaluation."""

    rooms: Tuple[DecisionRoom, ...]
    outdoor: DecisionOutdoor
    evaluated_at: datetime
    context: DecisionContext = field(default_factory=DecisionContext)


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """Sanitized, stable explanation entry."""

    code: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Normalized scores for the supported actions."""

    open: float = 0.0
    ventilate: float = 0.0
    close: float = 0.0
    none: float = 0.0
    penalties: Tuple[TraceEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class DataQualitySummary:
    """Inventory of accepted and rejected observations."""

    used: Tuple[str, ...] = ()
    discarded: Tuple[str, ...] = ()
    awaiting_source: Tuple[str, ...] = ()
    discarded_reasons: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """Pure core truth and delivery eligibility for one room."""

    room_id: str
    core_action: RecommendationAction
    delivered_action: RecommendationAction
    candidate_scores: CandidateScores = field(default_factory=CandidateScores)
    confidence: float = 0.0
    reason_code: str = "none"
    score: float = 0.0
    reason: str = ""
    target_perceived_c: float = 0.0
    indoor_perceived_c: float = 0.0
    outdoor_perceived_c: float = 0.0
    suggested_comfort_temperature_c: float = 0.0
    trace: Tuple[TraceEntry, ...] = ()
    data_quality: DataQualitySummary = field(default_factory=DataQualitySummary)
    delivery_suppressed_by: str | None = None
    evaluated_at: datetime | None = None
    baseline: str = "UNKNOWN"
    component_contributions: Tuple[TraceEntry, ...] = ()
    urgent: bool = False
    co2_ppm: float | None = None
    co2_influence: float = 0.0
    quality: Availability = Availability.AVAILABLE


@dataclass(frozen=True, slots=True)
class AggregateDecisionResult:
    """Deterministic aggregate result across rooms."""

    core_action: RecommendationAction
    delivered_action: RecommendationAction
    room_results: Tuple[DecisionResult, ...] = ()
    trace: Tuple[TraceEntry, ...] = ()
    evaluated_at: datetime | None = None
