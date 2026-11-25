"""Conservative heuristic impact estimation."""

from ..domain.decision_contracts import DecisionOption, DecisionRoom, DecisionSnapshot, RecommendationAction
from ..domain.impacts import ImpactEstimate
from ..calculations.psychrometrics import (
    absolute_humidity_g_m3,
    humidity_ratio_g_kg,
    pressure_hpa_or_default,
)


class HeuristicImpactEstimator:
    """Estimate directional mixing effects without inventing exact forecasts."""

    def __init__(self, *, horizon_minutes: int = 30) -> None:
        self.horizon_minutes = horizon_minutes

    def estimate(
        self,
        room: DecisionRoom,
        snapshot: DecisionSnapshot,
        candidate: DecisionOption,
    ) -> ImpactEstimate:
        if candidate.action not in {RecommendationAction.OPEN, RecommendationAction.VENTILATE}:
            return ImpactEstimate(self.horizon_minutes, confidence=1.0, assumptions=("window_remains_at_baseline",))
        indoor = room.temperature_c.value
        outdoor = snapshot.outdoor.temperature_c.value
        effect_factor = 0.25 if candidate.action is RecommendationAction.VENTILATE else 1.0
        temperature_delta = (
            0.0
            if indoor is None or outdoor is None
            else (float(outdoor) - float(indoor)) * effect_factor
        )
        indoor_humidity = room.humidity_percent.value if room.humidity_percent else None
        outdoor_humidity = snapshot.outdoor.humidity_percent.value if snapshot.outdoor.humidity_percent else None
        humidity_delta = 0.0 if indoor_humidity is None or outdoor_humidity is None else float(outdoor_humidity) - float(indoor_humidity)
        confidence = 1.0 if indoor is not None and outdoor is not None else 0.0
        moisture_delta = 0.0
        moisture_ratio_delta = 0.0
        if indoor is not None and outdoor is not None and indoor_humidity is not None and outdoor_humidity is not None:
            moisture_delta = (
                absolute_humidity_g_m3(float(outdoor), float(outdoor_humidity))
                - absolute_humidity_g_m3(float(indoor), float(indoor_humidity))
            ) * effect_factor
            pressure = snapshot.outdoor.pressure_hpa
            pressure_value = pressure.value if pressure is not None else None
            try:
                pressure_hpa, _ = pressure_hpa_or_default(
                    float(pressure_value) if pressure_value is not None else None
                )
                moisture_ratio_delta = (
                    humidity_ratio_g_kg(float(outdoor), float(outdoor_humidity), pressure_hpa)
                    - humidity_ratio_g_kg(float(indoor), float(indoor_humidity), pressure_hpa)
                ) * effect_factor
            except (TypeError, ValueError):
                moisture_ratio_delta = 0.0
        if candidate.action is RecommendationAction.VENTILATE:
            co2_delta = -500.0 if room.co2_ppm is not None else 0.0
        else:
            co2_delta = 0.0
        return ImpactEstimate(
            horizon_minutes=candidate.duration_minutes or self.horizon_minutes,
            temperature_delta_c=temperature_delta,
            moisture_delta_g_m3=moisture_delta,
            moisture_delta_g_kg=moisture_ratio_delta,
            humidity_delta_percent=humidity_delta,
            co2_delta_ppm=co2_delta,
            confidence=confidence,
            assumptions=("uniform_air_mixing", "directional_effect_only"),
        )
