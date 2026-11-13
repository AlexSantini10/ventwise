# DDP Software Architecture and Implementation Plan

The implementation should migrate incrementally from coupled scoring and
decision logic to a small deterministic pipeline. The core remains pure Python;
Home Assistant and external providers stay at the boundary.

## Target architecture

```text
Home Assistant and provider adapters
    | raw state, unit, quality, timestamp
    v
Canonical observations + room policy + decision memory
    v
DecisionEngine (pure orchestration, no I/O)
    | validation, constraints, candidates, estimator, objective, stabilizer
    v
DecisionResult + trace + reason codes
    v
Home Assistant presentation, entities, notification policy, diagnostics
```

Adapters resolve entities, configuration, weather, forecasts, polling,
persistence, output entities, and translations. The engine receives canonical
values and explicit memory; it never calls a sensor or provider.

## Domain contracts

Prefer frozen, slotted dataclasses and explicit annotations. The target model
includes `RawMeasurement`, `NormalizedMeasurement`, `IndoorState`,
`OutdoorState`, `ForecastPoint`, `EvaluationContext`, `Candidate`,
`ConstraintResult`, `ImpactEstimate`, `CandidateAssessment`, `DecisionResult`,
and `DecisionMemory`.

Time must be explicit in formulas and selectors. No domain calculation may
implicitly read system time.

The main variation points are narrow protocols:

```python
class ImpactEstimator(Protocol):
    def estimate(self, context, candidate, horizon_minutes) -> ImpactEstimate: ...

class ConstraintPolicy(Protocol):
    def evaluate(self, context, candidate) -> ConstraintResult: ...

class ObjectiveFunction(Protocol):
    def assess(self, context, baseline, candidate, constraints) -> CandidateAssessment: ...

class CandidateGenerator(Protocol):
    def generate(self, context) -> tuple[Candidate, ...]: ...
```

These are proposed contracts, not ready-to-run public APIs. Final names and
fields follow the canonical model when implementation begins. Sensor mapping,
unit resolution, and provider-specific logic stay in adapters. Pure formulas
remain stateless functions. The Home Assistant composition root selects
conservative default implementations and may select a calibrated estimator only
when valid local parameters exist.

## Logical module boundaries

```text
integration adapter       snapshot creation and provider mapping
coordinator               scheduling, I/O, cache, and persistence
configuration             config entry, options, and migrations
presentation              entities, translations, and notifications
core.models               DTOs, enums, and domain state
core.units                dimensional conversion
core.psychrometrics       pure physical formulas
core.validation           quality, freshness, and consistency
core.constraints          hard blocks, penalties, and precedence
core.candidates           baselines and adaptive durations
core.estimation           heuristic and calibrated estimators
core.objective            normalized discomfort and net benefit
core.stabilization        hysteresis and decision memory
core.engine               pure orchestration
core.diagnostics          reason codes and trace output
```

This is a logical decomposition, not a mandatory rename plan. Avoid churn and
keep cohesive small components together. Do not introduce a service locator,
circular imports, dynamic plugin discovery, formula DSL, or abstractions
without a real variation point.

## Cross-cutting rules

- Conversion uses a typed `(dimension, unit)` registry and rejects ambiguity.
- Current weather and forecast data remain distinct, with explicit valid times,
  provenance, and freshness thresholds.
- Local sensor preference applies only when valid; fallback is explicit and
  diagnosticable.
- Disabled CO2 removes that factor. Configured but stale CO2 produces a quality
  warning and never becomes evidence of good air.
- Unknown safety inputs fail closed for new openings, while optional non-safety
  data does not unnecessarily block every evaluation.
- RH comfort and humidity-ratio exchange remain separate to prevent double
  counting.
- Config-entry migrations are versioned, preserve room overrides, use safe
  defaults, and never log external credentials.

## Incremental delivery sequence

### Phase 0: characterization baseline

Freeze observable current behavior with deterministic timestamps and units.
Cover warm, cold, humid, high-CO2, severe-weather, pollen, stale-input, and
window-contact scenarios. Record intentional changes separately from regressions.

### Phase 1: canonical observations

Introduce raw and normalized measurements, quality, provenance, and source
selection. Add dimensional converters and adapter integration without changing
scoring. Equivalent units must produce equivalent decisions.

### Phase 2: isolated psychrometrics

Implement saturation pressure, vapor pressure, absolute humidity, humidity
ratio, and reconstructed RH as pure functions. Add dimensional, range,
monotonicity, and tabulated-value tests.

### Phase 3: constraints and safety

Implement structured hard, soft, and operational constraints with fail-closed
handling for unknown safety. Test severe weather versus IAQ, particulate
`BLOCK` versus CO2, and urgent close for a known open contact. Every blocker
must carry a reason and source.

### Phase 4: candidates and adaptive durations

Make the baseline depend on window state, generate bounded durations, apply
forecast buffers, and evaluate the common horizon. Test open, closed, unknown,
and precipitation-nearby states.

### Phase 5: estimation and objective

Add the heuristic estimator, normalized costs, baseline comparison, confidence
gate, and explainable alternatives. Add a calibrated physical estimator only
after the heuristic contract is stable and local parameters are available.

### Phase 6: stabilization and Home Assistant integration

Add hysteresis, persistence, rechecks, reason codes, diagnostics, translations,
entities, and notification policy. Cooldown applies to delivery, not safety
evaluation. Preserve existing configuration and automation compatibility.

### Phase 7: optional local calibration

Record opt-in local observations with configurable retention and deletion. Keep
training local with no automatic export. Estimate room parameters only when data
is sufficient, track confidence and drift, and fall back to heuristics when it
is not. Separate observed correlation from causal benefit because occupancy,
HVAC, solar gain, and other openings are confounders.

## Verification strategy

Unit tests cover formulas, conversions, null/NaN/infinite values, ranges,
constraints, precedence, discomfort bands, baseline scoring, and normalization.

Property and metamorphic tests cover equivalent-unit invariance, blocked
candidate exclusion, threshold behavior, critical-weather precedence, and
immutability of inputs.

Scenario tests cover temperature matrices, RH versus humidity ratio, rising CO2,
pollen and particulate policies, rain forecasts, multiple windows, unknown
contacts, stale sources, and conflicts between objectives.

Integration tests cover Home Assistant metadata, config flow and migrations,
provider failures, cache behavior, quiet hours, entities, diagnostics, and
translations using simulated APIs and no network dependency in core tests.

Regression and end-to-end checks compare old and new decisions on a fixed
dataset with every difference explained. Existing repository test, type, lint,
Hassfest, HACS, and Docker test-lab gates apply as appropriate to implementation.

## Definition of Done

- Modules have clear responsibilities and typed, minimal interfaces.
- Safety precedence is tested and no opening is recommended without verifiable
  safety inputs.
- Coefficients have declared units, meanings, and versioned defaults.
- Equivalent dimensional inputs preserve decisions.
- Results expose inputs, candidates, blockers, estimates, costs, and selection.
- Configuration compatibility is preserved unless a breaking migration is
  explicitly documented.
- Documentation and tests are updated with each behavior change.
- Future local persistence is opt-in, deletable, retention-controlled, and
  never exported by default.
