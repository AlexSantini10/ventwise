"""Estimated environmental impact contracts."""

from dataclasses import dataclass

from .decision_contracts import TraceEntry


@dataclass(frozen=True, slots=True)
class ImpactEstimate:
    """Estimated change caused by one candidate over a common horizon."""

    horizon_minutes: int
    temperature_delta_c: float = 0.0
    humidity_delta_percent: float = 0.0
    co2_delta_ppm: float = 0.0
    confidence: float = 0.0
    assumptions: tuple[str, ...] = ()
    evidence: tuple[TraceEntry, ...] = ()
    # Additive field kept after the original positional contract.
    moisture_delta_g_m3: float = 0.0
    # Additive pressure-aware moisture signal for psychrometric exchange.
    moisture_delta_g_kg: float = 0.0
