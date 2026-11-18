# VentWise v0.18 Decision Engine

This document describes the behavior implemented in the current repository.
It is intentionally more precise than the target DDP design documents: it
separates shipped behavior from capabilities planned for later releases.

## What the engine is

VentWise v0.18 uses one pure Python `DecisionEngine` as the authoritative
recommendation engine. It receives an immutable `DecisionSnapshot` and returns
an immutable `AggregateDecisionResult` containing one `DecisionResult` per
room, candidate scores, data-quality information, reason codes, and a trace.

The engine has no Home Assistant imports, network access, persistence, wall
clock reads, notification calls, or actuator calls. Home Assistant code builds
the snapshot and renders the result through existing entities and
notifications.

Implementation:

- `src/ventwise_core/decision.py`
- `src/ventwise_core/models.py`
- `custom_components/ventwise/application/runtime.py`
- `custom_components/ventwise/application/coordinator.py`

## Inputs used today

| Input | Used by v0.18 | Behavior |
| --- | --- | --- |
| Indoor temperature | Yes | Required for a room decision. |
| External temperature | Yes | One shared external reading for all room decisions; required for a room decision. |
| Indoor relative humidity | Yes, optional | Contributes to perceived comfort when valid. |
| External relative humidity | Yes, optional | Contributes to perceived external comfort and absolute-humidity exchange when valid. |
| Global target temperature | Yes | Default comfort target. |
| Per-room target temperature | Yes | Overrides the global target when enabled. |
| Per-room target humidity | Yes | Changes the comfort reference used by the objective. |
| External wind speed | Yes, optional | Supports opening at low speed and reduces opening benefit as speed rises. |
| External wind gust | Yes, optional | Uses the strongest available wind value and can trigger the hard wind block. |
| External weather condition | Yes, optional | Severe conditions force `CLOSE`. |
| Window contacts | Yes, core and integration layer | Known state participates in safety; unknown configured contacts block new opening. |
| Indoor CO2 | Yes, optional/configurable per room | Can independently request `VENTILATE` above the threshold; it never bypasses safety. |
| Quiet hours | Yes, integration layer | Suppress ordinary notification delivery. |
| Notification cooldown | Yes, integration layer | Suppress repeated ordinary notifications. |
| Evaluation timestamp | Yes | Makes freshness and deterministic replay explicit. |

Missing optional humidity is not replaced with `50%`. The decision remains
possible using temperature, but the result does not claim a humidity benefit.
Missing required temperatures produce `NONE` with `insufficient_evidence`.

## Canonical observation model

The adapter represents each value as an immutable `Observation` containing:

- value;
- canonical unit;
- observation timestamp;
- source identifier;
- availability state;
- validity state;
- optional freshness limit.

The engine records each input as `used`, `discarded`, or `awaiting_source` in
`DataQualitySummary`. It rejects values that are unavailable, invalid,
non-finite, out of plausible range, newer than the evaluation time, or stale.

Current canonical units are:

- temperature: `°C`;
- relative humidity: `%`;
- wind and gust: `m/s`.

The Home Assistant adapter converts state values into these units at the
single snapshot boundary while retaining source metadata for quality checks.

## Boundary normalization policy

The Home Assistant boundary accepts Celsius, Fahrenheit, and Kelvin
temperatures; percentage and ratio relative humidity; m/s, km/h, mph, and
knots wind speed; and declared pressure units (`hPa`, `Pa`, `kPa`, `bar`,
`atm`, `psi`, and `inHg`). Values are converted to Celsius, percent, m/s, and
hPa before a `DecisionSnapshot` is built. Unknown units, contradictory device
classes, non-numeric or non-finite values, and impossible ranges are invalid;
they are never silently converted or passed to the engine.

Home Assistant readings retain their source entity ID and `last_updated`
timestamp. Readings newer than the evaluation timestamp are discarded. Naive
timestamps are compared in the evaluation timestamp's timezone for legacy
compatibility; new adapters should provide timezone-aware timestamps. Manual
or synthetic values are explicitly marked with a `manual:` source and may use
the evaluation timestamp. Configured source selection is explicit and stable:
the selected override entity is used when configured, otherwise the selected
weather/forecast source is used, without relying on map iteration order.

`DataQualitySummary.discarded_reasons` records a stable `field:reason` entry
for each discarded value. Optional missing humidity remains awaiting source
and is never fabricated as `50%`; thermal-only decisions remain possible.

## Comfort calculation

For valid relative humidity, the v0.18 heuristic calculates a perceived
temperature approximation:

```text
perceived = temperature_c + clamp(
    (vapour_pressure - target_vapour_pressure) * 0.08,
    -3, +3
)
```

When relative humidity is missing, perceived temperature falls back to the
measured temperature only for that evaluation; the missing humidity remains
visible in the quality information.

The engine computes:

1. indoor distance from the target comfort point;
2. outdoor distance from the target comfort point;
3. absolute humidity for the volume-based moisture-exchange contribution;
4. the bounded CO2 contribution when enabled and valid;
5. the potential benefit of opening or closing;
6. a short ventilation score when outdoor air crosses the comfort band.

Relative humidity is not compared directly across different temperatures:
the perceived-temperature heuristic compares vapour pressure, while the
moisture-exchange objective uses absolute humidity in `g/mÂ³`. This remains a
bounded comfort heuristic, not a certified heat-index or PMV calculation.
Missing humidity or CO2 remains unknown and is recorded in data quality; no
value is fabricated.

The comfort band defaults to `±1°C` around the target. Scores are normalized
to `[0, 1]` and use smooth transitions rather than abrupt changes at ordinary
comfort boundaries.

This is a directional heuristic. It does not predict the future indoor
temperature or claim a percentage of air replacement.

## Candidate actions and selection

The engine evaluates three actionable candidates:

- `OPEN`: longer comfort-oriented opening;
- `VENTILATE`: short ventilation when outdoor air crosses the comfort band;
- `CLOSE`: outdoor conditions are less favorable or a hard safety condition is
  active.

`NONE` is returned when the benefit is too small, candidates are too close to
  one another, or required evidence is unavailable.

When CO2 is enabled and the room value is at or above the configured threshold
(1000 ppm by default), CO2 can independently select `VENTILATE`, even when the
external comfort score is worse. Hard safety blocks still take precedence.

Selection is deterministic:

1. hard safety blocks are evaluated before comfort selection;
2. scores below the meaningful-benefit threshold are rejected;
3. candidates within the configured winner margin are treated as tied;
4. remaining candidates are ordered by score and stable action ordering;
5. rooms are evaluated by `(room_id, name)`, never by input order.

The aggregate result selects the strongest actionable room. If no room is
actionable, all room results are retained for diagnostics and the aggregate
action is `NONE`.

## Safety behavior

Severe weather tokens such as thunder, lightning, storm, hail, tornado,
hurricane, and blizzard produce a hard safety result:

```text
core_action = CLOSE
delivered_action = CLOSE
reason_code = severe_weather
```

Wind is treated similarly when the effective wind value reaches the configured
block threshold. The effective value is the maximum of wind speed and gust.
Low wind can slightly support opening; intermediate wind reduces the opening
score.

Safety decisions are not represented as a large comfort penalty. They bypass
ordinary candidate scoring and retain an explicit blocker reason.

Weather and wind remain optional only when unconfigured. Once a safety source
is configured, missing, stale, invalid, future, or non-finite safety evidence
fails closed for new openings. A known-open contact under a hard safety block
produces an urgent `CLOSE`; delivery bypasses cooldown and stability. Quiet
hours are respected unless the user explicitly enables the safety notification
quiet-hours bypass. A configured but unknown contact never proves that a window is open
and therefore prevents a new `OPEN` or `VENTILATE` recommendation. It does not
hide an independent hard safety `CLOSE` recommendation.

## Home Assistant integration behavior

The coordinator is the composition root:

```text
HA states and config
    -> build_room_profiles()
    -> build_decision_snapshot()
    -> DecisionEngine.evaluate()
    -> decision_to_summary()
    -> decision_to_summary()  # direct core projection
    -> notification delivery projection
    -> HA entities and notifications
```

The engine never sends notifications. The core receives window state and
persisted action-guardrail state, returns explicit traces and updated state,
and remains the source of truth for all recommendation entities. The
application layer applies:

- quiet hours and notification cooldown;
- the user-configurable safety bypass for quiet hours;
- channel availability and notification stability;
- localized explanations and notification delivery.

VentWise remains recommendation-only. No result invokes a window, fan, HVAC,
ERV, or HRV service.

## Psychrometric support

The repository now contains pure, tested functions for:

- saturation vapor pressure;
- vapor pressure;
- absolute humidity in `g/m³`;
- humidity ratio in `g/kg` of dry air;
- RH reconstruction from absolute humidity;
- qualitative moisture exchange direction.

These functions are available through the core package. Humidity ratio is part
of the active v0.18 objective for moisture-exchange direction; absolute
humidity remains available for display and diagnostics.

## Not yet implemented in the active v0.18 path

The following capabilities belong to later DDP increments and must not be
described as current behavior:

- pressure-aware CO2 conversion from mass concentration;
- PM2.5, PM10, and pollen policies;
- short-term forecast safety and candidate-duration filtering;
- adaptive ventilation duration;
- window orientation and cross-ventilation;
- full immutable source timestamps from Home Assistant;
- calibrated room-impact estimation;
- advanced hysteresis and decision lockout in the core;
- golden replay datasets and cross-climate tuning.

## Testing contract

The v0.18 behavior is covered by:

- deterministic replay and room-order tests;
- missing, stale, invalid, non-finite, and implausible input tests;
- comfort, ventilation, severe-weather, and humidity-influence scenarios;
- psychrometric reference and domain tests;
- runtime adapter and coordinator regression tests;
- full repository tests where the platform supports the Home Assistant test
  framework.

When a future signal is added, it must be introduced through a canonical
observation, an explicit quality policy, a focused objective change, and
success/boundary/failure regression scenarios before it can affect actions.
## Decision and delivery boundary

The standalone `ventwise_core` package is the only implementation of domain
decisions. Home Assistant creates the canonical snapshot and exposes the core
result directly. Notification delivery is handled separately by the adapter:
quiet hours, stability, cooldown, duplicate suppression, and notifier
availability may suppress delivery, but must not change the core action, score,
reason code, trace, or data quality.
