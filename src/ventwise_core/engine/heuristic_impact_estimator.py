"""Conservative heuristic impact estimation."""

from ..domain.decision_contracts import DecisionOption, DecisionRoom, DecisionSnapshot, RecommendationAction
from ..domain.impacts import ImpactEstimate


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
        temperature_delta = 0.0 if indoor is None or outdoor is None else float(outdoor) - float(indoor)
        indoor_humidity = room.humidity_percent.value if room.humidity_percent else None
        outdoor_humidity = snapshot.outdoor.humidity_percent.value if snapshot.outdoor.humidity_percent else None
        humidity_delta = 0.0 if indoor_humidity is None or outdoor_humidity is None else float(outdoor_humidity) - float(indoor_humidity)
        co2_delta = -500.0 if room.co2_ppm is not None else 0.0
        confidence = 1.0 if indoor is not None and outdoor is not None else 0.0
        return ImpactEstimate(
            horizon_minutes=candidate.duration_minutes or self.horizon_minutes,
            temperature_delta_c=temperature_delta,
            humidity_delta_percent=humidity_delta,
            co2_delta_ppm=co2_delta,
            confidence=confidence,
            assumptions=("uniform_air_mixing", "directional_effect_only"),
        )
