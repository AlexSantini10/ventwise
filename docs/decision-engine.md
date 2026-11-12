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

The first pipeline increment preserves the existing thermal recommendation
actions (`open`, `ventilate`, `close`, and `none`) and current configuration
compatibility. Advanced CO2, absolute-humidity, particulate, pollen, forecast,
and contact semantics are introduced by their sequenced DDP issues rather than
being silently inferred here.

Operational suppression is represented separately from core truth. Quiet
hours, cooldown, and stability can suppress delivery while leaving the core
room decision and its trace intact. Notifications and any future actuator
integration remain outside the decision engine; VentWise is recommendation-only.

The legacy `ComfortRecommender` import is retained as a compatibility facade
that translates profiles into a snapshot and delegates to `DecisionEngine`.
It contains no independent decision rules.
