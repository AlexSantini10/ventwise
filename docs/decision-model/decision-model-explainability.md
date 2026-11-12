# VentWise Decision Model Explainability

This Markdown page is the written companion to the [decision model site](index.html). Start with the [HTML hub](index.html), use the [scenario page](scenarios.html) for the compact registry, and open the [full report](decision-model-report.html) for exhaustive tables. The pages are maintained directly; there is no generated DOCX or Python generator.

## Purpose

VentWise evaluates each configured room independently and returns `open`, `ventilate`, `close`, or `none`. It is local, deterministic, explainable, and advisory. It never controls a physical device and never invents a missing observation.

The implementation sources are:

- [`models.py`](../custom_components/ventwise/ventwise_core/models.py) for observations, rooms, outdoor data, results, and defaults.
- [`decision.py`](../custom_components/ventwise/ventwise_core/decision.py) for validation, precedence, transformations, scoring, duration, and delivery separation.
- [`runtime.py`](../custom_components/ventwise/application/runtime.py) for Home Assistant configuration, entity references, provider inputs, and debug exposure.

## Reading order

1. Start at the [HTML hub](index.html) and choose the topic page.
2. Use [inputs and quality](inputs.html) and the [full report](decision-model-report.html) to identify every field, unit, provenance requirement, and missing-data behavior.
3. Use the [scenario registry](scenarios.html) to check whether a case is already covered.
4. For an unlisted case, copy the proposal template from [operations](operations.html) into a GitHub issue or pull request.

## Decision precedence

1. Missing or stale critical outdoor temperature, condition, or wind fails closed for opening and ventilation.
2. Severe weather and active precipitation block opening and ventilation.
3. Unsafe wind or gusts block opening and ventilation.
4. Explicit exposure `avoid` policies block opening and ventilation.
5. Exposure `reduce` policies and imminent rain penalize candidates.
6. Thermal comfort, moisture, and CO2 evidence produce candidate scores.
7. Forecast and physical context adjust duration, confidence, or explanation but cannot override safety blocks.
8. Window state, stability, cooldown, and quiet hours affect delivery only.

The model is intentionally bidirectional: a cold room can produce `open` when
outside air is warmer and closer to target; a hot room can produce `open` when
outside air is cooler and closer to target. If outside air moves the room toward
the target but would be a poor stable endpoint, the result is bounded
`ventilate`. If outside is worse in the relevant direction, the result is
`close` when the difference is meaningful.

## What must be kept synchronized

When the model changes, update all of the following in the same change:

- the exhaustive parameter tables in the HTML;
- the written explanation here if the behavior or interpretation changes;
- the scenario registry, including expected core and delivered actions;
- the narrowest relevant regression test;
- the model version or source link when its meaning changes.

CI checks that both pages exist and contain the required model, parameter, scenario, and proposal sections. It intentionally does not regenerate the HTML: the documentation is maintained directly so the visual explanation remains readable and reviewable.

## Scenario registry

The registry below is a compact Markdown index of the executable contract. The
HTML report carries the complete evidence and precedence columns; both pages
must remain synchronized with the tests.

| Scenario family | Expected core action | Expected delivered action | Coverage |
| --- | --- | --- | --- |
| Hot/cold room with outdoor air closer to target | `open` | Same unless delivery is gated | Implemented and tested |
| Outdoor air moves toward target but is a poor stable endpoint | `ventilate` for 15/10/5 minutes | Same unless delivery is gated | Implemented and tested |
| Outdoor air materially worsens comfort | `close` | Same unless the window is already closed | Implemented and tested |
| Neutral conditions | `none` | `none` | Implemented and tested |
| High humidity or high/rising CO₂ | `ventilate` | Same unless delivery is gated | Implemented and tested |
| Rain, storm, unsafe wind/gusts, or exposure `avoid` | `close` | `close`; quiet-hours delivery is configurable and defaults to suppressed | Implemented and tested |
| Exposure `reduce` with matching unit and averaging period | Penalized candidate | Core preserved | Implemented and tested |
| Missing, invalid, future, stale, or implausible critical data | `none` or safety `close` | Core preserved | Implemented and tested |
| Condensation risk | Core preserved | Duration capped at 5 minutes; confidence reduced | Implemented and tested |
| Window contacts, quiet hours, cooldown, or stability | Core preserved | Delivery may become `none` | Implemented and tested |
| Multi-room evaluation | Best actionable room selected | Per-room results preserved | Implemented and tested |

Coverage labels are evidence claims: `implemented and tested` means a named
unit or integration regression exists in the repository. No row is a promise
that an unimplemented behavior is planned.

## New scenario proposal template

```text
Scenario name:
Room and outdoor inputs:
Source, unit, averaging window, and freshness:
Expected core_action:
Expected delivered_action:
Which existing rule wins or what new precedence is needed:
Expected trace / reason code:
Missing-data behavior:
Regression test name:
Safety or privacy implications:
```

## Limits

- Advisory only: not a medical, safety, security, weather-protection, or regulatory system.
- CO2 is a ventilation indicator, not a universal indoor-air-quality or health threshold.
- Room physics are not an exact airflow calibration.
- Forecast and Open-Meteo/CAMS exposure values remain model data with provenance.
- Missing data stays missing; no occupancy, airflow, or hazard is invented.
