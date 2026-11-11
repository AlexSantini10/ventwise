# VentWise Decision Model Explainability

This Markdown page is the written companion to the [visual decision model report](decision-model-report.html). The HTML is maintained directly; there is no generated DOCX or Python generator.

## Purpose

VentWise evaluates each configured room independently and returns `open`, `ventilate`, `close`, or `none`. It is local, deterministic, explainable, and advisory. It never controls a physical device and never invents a missing observation.

The implementation sources are:

- [`models.py`](../custom_components/ventwise/ventwise_core/models.py) for observations, rooms, outdoor data, results, and defaults.
- [`decision.py`](../custom_components/ventwise/ventwise_core/decision.py) for validation, precedence, transformations, scoring, duration, and delivery separation.
- [`runtime.py`](../custom_components/ventwise/application/runtime.py) for Home Assistant configuration, entity references, provider inputs, and debug exposure.

## Reading order

1. Follow the visual pipeline in the [HTML report](decision-model-report.html).
2. Use its exhaustive data tables to identify every field, unit, provenance requirement, and missing-data behavior.
3. Use the scenario registry to check whether a case is already covered.
4. For an unlisted case, copy the proposal template at the end of the HTML page into a GitHub issue or pull request.

## Decision precedence

1. Missing or stale critical outdoor temperature, condition, or wind fails closed for opening and ventilation.
2. Severe weather and active precipitation block opening and ventilation.
3. Unsafe wind or gusts block opening and ventilation.
4. Smoke alerts and explicit exposure `avoid` policies block opening and ventilation.
5. Exposure `reduce` policies and imminent rain penalize candidates.
6. Thermal comfort, moisture, and CO2 evidence produce candidate scores.
7. Forecast and physical context adjust duration, confidence, or explanation but cannot override safety blocks.
8. Window state, stability, cooldown, and quiet hours affect delivery only.

## What must be kept synchronized

When the model changes, update all of the following in the same change:

- the exhaustive parameter tables in the HTML;
- the written explanation here if the behavior or interpretation changes;
- the scenario registry, including expected core and delivered actions;
- the narrowest relevant regression test;
- the model version or source link when its meaning changes.

CI checks that both pages exist and contain the required model, parameter, scenario, and proposal sections. It intentionally does not regenerate the HTML: the documentation is maintained directly so the visual explanation remains readable and reviewable.

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
- Missing data stays missing; no occupancy, airflow, HVAC state, or hazard is invented.
