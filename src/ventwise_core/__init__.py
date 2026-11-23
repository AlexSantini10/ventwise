"""Standalone, deterministic VentWise decision core."""

from .domain.decision_contracts import (
    AggregateDecisionResult,
    Availability,
    CandidateScores,
    OptionEvaluationContext,
    DecisionOption,
    ComfortObservation,
    DataQualitySummary,
    DecisionRuntimeContext,
    DecisionOutdoor,
    ExternalConditions,
    DecisionResult,
    DecisionRoom,
    DecisionSnapshot,
    ForecastObservation,
    Observation,
    RecommendationAction,
    RecommendationSummary,
    RoomObservation,
    SourceReading,
    RoomProfile,
    RoomGuardrailState,
    RoomRecommendation,
    SeasonMode,
    TraceEntry,
    ExpectedEffect,
    OptionEligibility,
    OptionEvaluation,
    Validity,
)
from .engine.decision_engine import DecisionConfig, DecisionEngine
from .domain.baseline import BaselineAssessment, BaselineState
from .domain.impacts import ImpactEstimate
from .domain.objectives import ObjectiveAssessment, ObjectiveContribution
from .engine.baseline_assessor import DefaultBaselineAssessor
from .engine.heuristic_impact_estimator import HeuristicImpactEstimator
from .domain.results import CandidateAssessment, SelectionResult
from .engine.candidate_selector import HighestNetBenefitSelector
from .engine.objective_registry import (
    CarbonDioxideObjective,
    MoistureExchangeObjective,
    ObjectiveRegistry,
    ThermalComfortObjective,
)
from .engine.evaluation_pipeline import (
    DecisionOptionGenerator,
    OptionEligibilityPolicy,
    ExpectedEffectEstimator,
    DecisionOptionScorer,
)
from .calculations.psychrometrics import (
    DEFAULT_PRESSURE_HPA,
    absolute_humidity_g_m3,
    humidity_ratio_g_kg,
    humidity_ratio_g_kg_from_relative_humidity,
    moisture_exchange_direction,
    pressure_hpa_or_default,
    perceived_temperature_c,
    relative_humidity_percent_from_absolute,
    relative_humidity_percent_from_humidity_ratio,
    saturation_vapor_pressure_hpa,
    vapor_pressure_hpa,
)
from .serialization.json_codec import (
    SCHEMA_VERSION,
    aggregate_result_to_dict,
    config_to_dict,
    evaluate_scenario,
    result_to_dict,
    snapshot_from_dict,
    snapshot_to_dict,
)

__all__ = [
    "ComfortObservation", "AggregateDecisionResult", "Availability",
    "CandidateScores", "DataQualitySummary", "DecisionConfig",
    "OptionEvaluationContext", "DecisionOption", "ExpectedEffect",
    "OptionEligibility", "OptionEvaluation", "DecisionOptionGenerator",
    "OptionEligibilityPolicy", "ExpectedEffectEstimator", "DecisionOptionScorer",
    "DecisionRuntimeContext", "DecisionEngine", "DecisionOutdoor",
    "BaselineAssessment", "BaselineState", "ImpactEstimate",
    "ObjectiveAssessment", "ObjectiveContribution", "ObjectiveRegistry",
    "ThermalComfortObjective", "MoistureExchangeObjective", "CarbonDioxideObjective",
    "DefaultBaselineAssessor", "HeuristicImpactEstimator",
    "CandidateAssessment", "SelectionResult", "HighestNetBenefitSelector",
    "ExternalConditions", "DecisionResult", "DecisionRoom",
    "DecisionSnapshot", "ForecastObservation", "Observation",
    "RecommendationAction", "RecommendationSummary", "RoomObservation",
    "SourceReading", "RoomProfile", "RoomGuardrailState", "RoomRecommendation", "SeasonMode",
    "TraceEntry", "Validity", "DEFAULT_PRESSURE_HPA",
    "absolute_humidity_g_m3", "humidity_ratio_g_kg",
    "humidity_ratio_g_kg_from_relative_humidity", "moisture_exchange_direction",
    "pressure_hpa_or_default", "perceived_temperature_c",
    "relative_humidity_percent_from_absolute",
    "relative_humidity_percent_from_humidity_ratio",
    "saturation_vapor_pressure_hpa", "vapor_pressure_hpa",
    "SCHEMA_VERSION", "aggregate_result_to_dict", "config_to_dict",
    "evaluate_scenario", "result_to_dict", "snapshot_from_dict",
    "snapshot_to_dict",
]
