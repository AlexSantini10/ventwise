# DDP Architecture and Decision Pipeline

The Deterministic Decision Pipeline (DDP) is the target architecture for
VentWise recommendations. It describes intended behavior and contracts; it
does not claim that every stage is implemented in the current integration.

## Purpose and invariants

For one room, the DDP chooses among `OPEN`, `VENTILATE`, `CLOSE`, and `NONE`
using environmental observations, forecasts, configuration, window state, and
the expected net benefit against maintaining the current state. These are
recommendation intents, not automatic window controls.

The following invariants are mandatory:

1. A hard constraint prevents opening even when the estimated benefit is high.
2. If opening safety cannot be verified, the system must not recommend opening
   and must identify the missing or unreliable input.
3. CO2 is a separate IAQ dimension. It never overrides safety or outdoor-air
   quality blocks.
4. Every candidate is compared with a comparable baseline over the same horizon.
5. Missing data is never treated as zero or as evidence of good conditions.
6. Stabilization and cooldown must not delay a critical close warning when an
   open window is known.
7. The core has no dependency on Home Assistant, APIs, databases, or networks.
8. The engine recommends; it does not create automations that operate windows.

The same inputs, configuration, current time, and prior decision state must
produce the same result. Results must be explainable and testable.

## End-to-end pipeline

```text
Sources (sensors, weather, forecast, configuration)
  -> ingestion and dimensional normalization
  -> validation, quality, and immutable evaluation snapshot
  -> hard constraints and soft constraints
  -> candidates and baseline
  -> impact estimation over a common horizon
  -> net-benefit scoring and confidence gate
  -> selection, window state, and stabilization
  -> diagnostics, recommendation, and notification eligibility
```

Environmental evaluation and notification delivery are separate concerns.
Quiet hours and cooldowns can suppress non-critical delivery, but must not
change the engine's environmental result.

## Pipeline stages

### Ingestion and normalization

Adapters accept raw values with value, unit, dimension or device class, source
identifier, timestamp, and provenance. Forecast points carry their valid time.
Adapters produce canonical measurements such as degrees Celsius, RH percentage,
ppm, metres per second, hPa, micrograms per cubic metre, and humidity ratio.

Only conversions known for the declared dimension are allowed. Unknown units,
missing units, incompatible device classes, and ambiguous percentages become
`INVALID`; the adapter must never guess fraction versus percentage. Every value
retains source, timestamp, original unit, observed/forecast/estimated type, and
quality.

Source precedence is configurable. A valid local sensor may take precedence
over a compatible weather provider, with an explicit and diagnosticable
fallback. Incompatible timestamps must not be silently mixed.

### Validation and evaluation snapshot

Validation checks finite values, plausible ranges, timezone-aware timestamps,
per-source freshness, and temporal consistency. Quality is explicit, for
example `VALID`, `ESTIMATED`, `STALE`, `MISSING`, or `INVALID`, with a reason.

An unconfigured optional factor is different from a configured but unusable
factor. Quality and confidence propagate through an immutable
`EvaluationContext`. Missing, stale, or invalid required safety data fails
closed for new openings. Missing optional CO2 reduces the quality gate; it is
not evidence that air quality is good.

### Constraints

Each candidate receives `allowed`, hard blockers, soft penalties, and
uncertainty. A hard blocker excludes a candidate before scoring; it is not a
very large penalty.

Typical hard constraints include severe weather, hail, smoke, excessive gusts,
configured rain policy, and configured pollen or particulate `BLOCK` policy.
Soft constraints include moderate wind, `REDUCE` outdoor-quality policy, energy
cost, comfort deterioration, noise, and explicit preferences.

If a known open contact is exposed to a newly active hard constraint, `CLOSE`
has immediate priority and bypasses ordinary persistence and notification
cooldown. An unknown contact state must request verification rather than claim
that a window is open or closed. With multiple windows, the close recommendation
is associated with each affected known-open contact; unknown contacts remain
unknown.

If high CO2 requires ventilation but all natural ventilation candidates are
blocked, report an unmet need and its blocker. A separate mechanical solution
may be suggested when available, but the engine must not recommend opening.

### Baseline and candidates

The baseline depends on the actual state:

- closed: `KEEP_CLOSED`, plus bounded `OPEN` and `VENTILATE` durations;
- open: `KEEP_OPEN`, `CLOSE_NOW`, and optionally a scheduled close;
- unknown: no unverifiable new opening, with state verification diagnostics.

Initial candidate durations may be 5, 10, 20, and 30 minutes. Candidates are
filtered against hard constraints and forecast safety before impact estimation.
The common horizon is initially 30 minutes. After an action ends, the expected
post-action state is simulated so short and long candidates remain comparable.

`OPEN` represents a longer comfort-oriented opening. `VENTILATE` represents a
shorter air-exchange intent, often for IAQ or humidity. Neither promises
complete air replacement.

### Impact estimation

`HeuristicImpactEstimator` is the initial proposed estimator. It reports
direction, normalized magnitude, and confidence for temperature, humidity, and
CO2 without inventing future degrees or ppm values that the model cannot
justify.

`CalibratedImpactEstimator` is a later option. It may produce trajectories
using local air-exchange rate, thermal inertia, occupancy, and other validated
parameters. It must return assumptions, confidence, and an explicit fallback.

Temperature, humidity ratio, reconstructed RH, CO2, and outdoor-quality effects
are estimated separately. A CO2 decrease from mixing does not imply the same
thermal response.

### Selection and stabilization

The engine selects the highest-benefit admissible candidate. It activates that
recommendation only when the benefit exceeds its threshold and the quality gate
passes. Otherwise it returns the baseline or `NONE`, with reasons and unmet
needs.

Hysteresis, minimum persistence, room lockout, and notification cooldown reduce
oscillation. Critical close recommendations bypass these filters. Re-evaluate
when contacts, hard constraints, or critical inputs change; never treat a prior
recommendation as proof of the real window state.

### Explainable output

A `DecisionResult` should contain action, duration, priority, stable reason
codes, net benefit, component contributions, penalties, baseline, rejected
alternatives, confidence, input quality, missing inputs, constraints, forecast
risk, unmet needs, room identifier, evaluation time, validity/recheck time,
contact state, and notification eligibility.

Home Assistant adapters turn reason codes into localized text. Structured
diagnostics must not include secrets, tokens, or unnecessary location data.

## Representative decisions

| Situation | Expected result |
| --- | --- |
| Warm room, cooler outdoor air, no blockers, window closed | `OPEN` if benefit clears the threshold |
| High CO2, outdoor air thermally costly, no blocker | Short `VENTILATE` if IAQ benefit exceeds cost |
| Higher outdoor RH but lower outdoor humidity ratio | Favor exchange when the mass-based model predicts drying |
| Comfort and CO2 within configured ranges | `NONE` |
| Severe weather and known open window | Immediate `CLOSE` |
| Severe weather and closed window | No opening; report unmet IAQ needs if relevant |
| Safety weather unavailable | No opening; report that safety is unverifiable |
| Rain forecast during a long candidate | Reject affected long durations; assess shorter safe options |

## Configuration and responsibility

Global preferences may be overridden per room: comfort bands, CO2 activation,
weights, pollen and particulate policies, wind and rain policies, energy
priority, duration bounds, stability, quiet hours, and cooldown. Configuration
schema changes must be versioned. Season mode may change targets or energy
preference, but not physical laws.

The DDP provides explainable heuristic recommendations for complex environments;
it is not a medical, safety, security, weather-protection, or automatic-control
system. Local calibration may improve estimates, but cannot guarantee outcomes.
