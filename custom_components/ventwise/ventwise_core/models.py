"""Core data models for VentWise recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class RecommendationAction(str, Enum):
    """Action that the recommender can return."""

    OPEN = "open"
    CLOSE = "close"
    NONE = "none"


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
    target_temperature_c_override: float | None = None


@dataclass(frozen=True, slots=True)
class ComfortObservation:
    """Outdoor or target comfort context."""

    temperature_c: float
    humidity_percent: float
    wind_speed_m_s: float | None = None


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Tunable scoring parameters."""

    target_temperature_c: float = 22.0
    soft_outdoor_threshold_c: float = 22.0
    minimum_score: float = 0.35
    minimum_stability_seconds: int = 0
    neutral_band_c: float = 0.4
    score_scale_c: float = 8.0
    humidity_weight: float = 0.04
    wind_open_preference_threshold_m_s: float = 4.0
    wind_open_preference_per_m_s: float = 0.02
    wind_open_penalty_per_m_s: float = 0.05
    soft_threshold_penalty: float = 0.7
    season_mode: SeasonMode = SeasonMode.AUTO
    open_bias: float = 0.0
    close_bias: float = 0.0


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
    indoor_perceived_c: float
    outdoor_perceived_c: float
    room_id: str | None = None
    open_score: float = 0.0
    close_score: float = 0.0


@dataclass(frozen=True, slots=True)
class RecommendationSummary:
    """Result returned by the core engine."""

    action: RecommendationAction
    score: float
    reason: str
    room_recommendations: Tuple[RoomRecommendation, ...] = field(default_factory=tuple)
    blocked_by: str | None = None
    best_room: str | None = None
