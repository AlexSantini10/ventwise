# Deterministic Decision Pipeline

VentWise evaluates recommendations through five explicit boundaries:

```text
Home Assistant state
    -> runtime normalization
    -> immutable DecisionSnapshot
    -> pure DecisionEngine
    -> RecommendationSummary rendering
    -> notification delivery
```

`DecisionEngine.evaluate(snapshot)` is deterministic: the same snapshot and
`DecisionConfig` produce the same room ordering, action, score, and trace. The
engine receives `evaluated_at` in the snapshot and therefore never reads the
wall clock. It has no Home Assistant or network dependency and does not mutate
delivery state.

Validated humidity readings are also used for moisture reasoning. Absolute
humidity is calculated with the Magnus equation (`a=17.62`, `b=243.12`) and
expressed in g/m³. The moisture delta is indoor minus outdoor absolute
humidity: positive values indicate drying potential and negative values indicate
humidifying potential. Moisture-only ventilation requires a meaningful delta of
at least 1.0 g/m³ plus a 10 percentage-point indoor RH boundary from the target.
It produces an advisory `VENTILATE` recommendation for 10 minutes.

Precedence remains: invalid or unavailable critical data; severe weather or
unsafe wind; thermal safety/comfort; moisture-only ventilation when thermal
conditions are neutral; and no recommendation for insignificant moisture
difference. Missing or invalid humidity omits moisture scoring without
inventing a fallback value or removing a valid thermal recommendation.

The pipeline preserves the existing thermal recommendation actions (`open`,
`ventilate`, `close`, and `none`) and current configuration compatibility.

Operational suppression is represented separately from core truth. Quiet
hours, cooldown, and stability can suppress delivery while leaving the core
room decision and its trace intact. Notifications and any future actuator
integration remain outside the decision engine; VentWise is recommendation-only.

The legacy `ComfortRecommender` import is retained as a compatibility facade
that translates profiles into a snapshot and delegates to `DecisionEngine`.
It contains no independent decision rules.
