# Canonical decision-engine contract

## Purpose and limits

This is VentWise's canonical decision-engine contract. It defines data,
precedence, formulas, initial thresholds, outputs, and tests.

The engine is local, deterministic, explainable, and advisory. Equal normalised
input, configuration, and evaluation time produce the same result and trace.
Historical estimates are explicit models, not machine learning. VentWise advises
but does not control windows or devices; it is not a medical, safety,
weather-protection, security, or physical-control system. Health thresholds are
context, not diagnoses, domestic regulatory limits, or safety guarantees.

> [!IMPORTANT]
> **Advice only.** The engine can recommend an action; it must never operate a
> physical device, replace a safety system, or present an air-quality signal as
> a medical conclusion.

Future data is **active** (needed now), **optional** (improves a decision), or
**reserved** (catalogued, unsupported). Missing reserved data never enables
risky advice.

## Flow and actions

> **1. Acquire** → **2. Validate** → **3. Block unsafe cases** →
> **4. Apply preferences** → **5. Simulate** → **6. Score** →
> **7. Select action** → **8. Apply delivery guardrails** → **9. Explain**

Acquisition retains value, unit, source, timestamp, and quality. Validation
converts units and rejects invalid data. Blocks apply precedence. Preferences
cannot override blocks. Simulation evaluates 15, 30, 60, and 120 minutes when
sufficient data exists. Scoring selects a meaningful action; delivery guardrails
then regulate its presentation. Explanation exposes all material facts.

| Action | Meaning |
|---|---|
| **open** | Stable net benefit without a required short duration. |
| **ventilate** | Air out for a proposed duration, then reassess. |
| **close** | Opening is harmful or protection is required. |
| **none** | No meaningful benefit or already consistent state. |

`ventilate` duration is deliberately bounded generic guidance: 15 minutes
without a usable forecast, 10 with one, and 5 where an imminent-rain forecast
applies. Room volume, opening area, resistance and mass are not treated as an
airflow calibration; complete parameters can reduce confidence, while
condensation risk can cap the generic duration at five minutes. Below the
warm-domain heat-index boundary the thermal comparison is dry-bulb only; it
does not claim a cold/wind-chill model.

Current precipitation is an immediate safety block, distinct from forecast
precipitation probability. Outdoor humidity is optional: absent or invalid
humidity removes apparent/moisture scoring but does not suppress safe
temperature-only advice. Temperature, weather condition and wind remain
safety-critical. Future-dated, stale, non-finite and source-implausible
readings are discarded with their provenance retained in data quality.

> [!TIP]
> Read **At-a-glance ordered decision table** first. It is the shortest route
> to the engine's actual decision priority and user-facing wording.

An urgent **close** remains in the core result; a window contact can say that
the window is already closed but cannot erase the recommendation.

## Implemented deterministic interface

The reusable core exposes `DecisionEngine` for new adapters. Its immutable
`DecisionSnapshot` contains source-neutral `Observation` values; every value
has canonical unit, source, observation/receipt time, validity, freshness and
availability. `awaiting_source` is retained rather than guessed.

`DecisionResult` always retains both `core_action` (the physical advice) and
`delivered_action` (what may be shown after contacts, quiet hours, cooldown,
or stability). Its ordered trace, candidate scores, blocks, penalties and data
quality summary are stable test/UI/log interfaces. Legacy Home Assistant
configuration continues to use the existing compatibility scorer while entity
adapters migrate to snapshots; no configured entity or threshold is dropped.

## At-a-glance ordered decision table

This is the authoritative reading order. A higher row always wins. The final
column is the required user-facing explanation pattern.

| Priority | Data / condition | Class | How it is used | Core result | Explanation |
|---:|---|---|---|---|---|
| 1 | Missing, invalid, or stale critical weather | 🛑 **Blocking** | Fail closed before scoring | Never open/ventilate | “Cannot safely recommend opening: weather data is unavailable or stale.” |
| 2 | Thunderstorm, lightning, hail, tornado, hurricane, dangerous ice/snow, severe alert | 🛑 **Blocking** | Safety gate | Block open/ventilate; close when applicable | “Close or keep closed because severe weather is current or imminent.” |
| 3 | Wind or gust above technical threshold | 🛑 **Blocking** | Opening-safety gate | Block open/ventilate; close if known open | “Gusts exceed the configured safe-opening threshold.” |
| 4 | Outdoor pollution, smoke/wildfire, or pollen beyond profile | 🛑 / 🟠 **Block / penalty** | Exposure policy; comfort cannot override | Block or reduce | “Fresh-air benefit is overridden by outdoor air quality or pollen.” |
| 5 | Degraded indoor CO₂ or IAQ | 🟢 / 🟠 **Benefit / penalty** | Ventilation need after 1–4 pass | Favour ventilate | “Indoor air needs renewal, subject to outdoor conditions.” |
| 6 | Temperature, absolute humidity, condensation | 🟢 / 🟠 **Benefit / penalty** | Physical net benefit and duration | Open, ventilate, close, or none | “Outdoor air is expected to improve/worsen temperature or moisture.” |
| 7 | Forecast, local trend, room model | 🔵 **Informational** | Duration, future opportunity, confidence | Cannot override 1–4 | “Forecast changes expected duration or confidence.” |
| 8 | Quiet hours, cooldown, stability, contacts | 🟣 **Delivery guardrail** | Post-core delivery only | May suppress delivery | “Core advice is X; delivery is suppressed because Y.” |

## Complete data catalogue

Legend: 🛑 **B** blocking, 🟠 **P** strong penalty, 🟢 **V** benefit signal,
🔵 **I** informational only, 🟣 **G** delivery guardrail. I/E means indoor/outdoor.
“Future” means reserved.

| Family | Data, unit, I/E | Intended source | Status and transformation | Priority / action effect | Fallback and explanation |
|---|---|---|---|---|---|
| Thermal comfort | temperature °C, I/E | room sensor; weather/sensor | active; validate, short average, apparent T | B/V; thermal comparison, stale E blocks opening | no thermal score; “indoor temperature unavailable” / never open if E is stale |
| Thermal comfort | apparent temperature °C, I/E; target °C, season | derived; preference/calendar | active/optional; T+RH, valid outdoor wind, target band | V/I; benefit and context, never block | use T at lower confidence; show default target |
| Thermal comfort | radiation W/m², cloud %, HVAC state, internal gains W | weather; equipment/estimate | optional; future loads for RC model | P/I; anticipate heating/cooling | ignore or never infer HVAC state |
| Humidity and condensation | RH %, AH g/m³, dew point °C, ΔAH g/m³ | sensor/weather, Magnus | active; RH valid 0–100% | V; dry E favours ventilate | no moisture benefit without RH |
| Humidity and condensation | condensation/mould risk | derived + surface temperature | optional | P; changes duration/benefit | “risk not estimated” without surface data |
| Air exchange | CO₂ ppm I/E, trend ppm/h, volume m³ | sensor/provider; configuration | active I, optional E/volume; delta/trend | V; high indoor CO₂ favours ventilate | conservative duration; no inferred occupancy |
| Air exchange | occupancy, ACH h⁻¹, window state | presence/model/contact | future/future/optional | I/V/G; model or delivery | trend/state unknown is explicit; contact never changes core |
| Pollution | AQI index; PM2.5/PM10 µg/m³ I/E | provider/sensor | optional; retain standard and averaging window | P; high outdoor values block/reduce | never compare different indices; lower confidence without average |
| Pollution | NO₂, O₃, CO, SO₂; VOC/TVOC; formaldehyde | provider/sensor | future; retain unit, average, sensor type | P; high E blocks/reduces; high I favours safe ventilation | no conversion without T/P; no generic health equivalence |
| Pollution | smoke/wildfire; quality summary I/E | provider/derived | optional/future; event plus causal measure | B/P/I; block/reduce/explain | never claim an event without source |
| Allergens | pollen by species grains/m³, species, personal threshold | Open-Meteo/CAMS; preference | optional; species/horizon filter | B/P; reduce or avoid | no pollen block if absent; lower confidence |
| Allergens | profile ignore/reduce/avoid | preference | active policy | I/P/B; ignore informational, reduce penalty, avoid block | explicit default: reduce |
| Weather and risk | condition, rain mm/probability %, wind/gust m/s, direction | weather | active; normalise current/imminent, max gust | B/P/I; rain/wind block, direction refines | stale/missing critical weather: never open |
| Weather and risk | alerts, storm/lightning/hail, snow/ice/tornado/hurricane | official source/weather | active/optional; severity and validity | B; blocks and may close | never downplay alert or infer it |
| Prediction | forecast, local trend, age, completeness | weather/series/metadata | optional/active; 15–120 min | I/P/V/B; duration/confidence; critical stale blocks | trace every discarded input |
| Prediction | thermal/humidity/CO₂ model | local calibration | future; RC/mass balance | I/V; duration/opportunity | documented conservative default |
| Room/building | insulation, mass, opening size/orientation, exposure, cross ventilation | configuration | future; C/R/airflow factor | I/V; simulation and wind exposure | no false precision |
| Preferences/delivery | pollution sensitivity, thresholds, quiet hours, cooldown, stability, known open/closed | preference/contact | active/optional; policy/guardrail | P/V/G; personalize; delivery only | show preset or suppression cause |

## Validation, formulas, and simulation

Canonical internal units are °C, %, g/m³, ppm, µg/m³, m/s, mm, W/m², m³,
and seconds. Each reading retains precision, source, and timestamp. RH and
probability must be 0–100%; volume >0; precipitation, radiation, and
concentration ≥0. T, wind, and concentration also have sensor-specific
plausibility ranges. Invalid values are rejected, never silently clipped.

Initial configurable freshness: indoor 15 min, critical weather 15 min,
forecast 90 min from issue time. The trace always reports value age and limit.

### Apparent temperature

For the warm domain, T in °C and RH in percent:

```text
HI = -8.784695 + 1.61139411T + 2.338549RH - 0.14611605T·RH
     - 0.012308094T² - 0.016424828RH² + 0.002211732T²·RH
     + 0.00072546T·RH² - 0.000003582T²·RH²
```

Outside that domain the initial value is T with reduced confidence until a
validated unified hot/cold index exists. Wind never penalises indoor
temperature; it may later enter outdoor apparent temperature in its domain.

### Magnus humidity formula

With a=17.62 and b=243.12 °C:

```text
γ   = ln(RH/100) + aT/(b + T)
Tdp = bγ/(a - γ)
es  = 6.112 · exp(17.62T/(243.12 + T))
e   = RH/100 · es
AH  = 216.7 · e/(T + 273.15) g/m³
```

ΔAH = AH_E − AH_I is more useful than RH alone: ΔAH<0 means outdoor air removes
vapour. Condensation is estimated only when indoor dew point approaches an
estimated surface temperature; absent surface data is not “no risk”.

### Thermal RC model and mass balance

For a step Δt:

```text
T(t+Δt) = T(t) + Δt/C · [ (T_E − T_t)/R + Q_HVAC + Q_solar
                           + Q_internal + H_v(T_E − T_t) ]
```

R is resistance, C thermal mass, H_v ventilation conductance, and Q power.
Without local calibration, the model limits duration and confidence, never
promises a temperature.

For room volume V, air exchange λ (s⁻¹), source G, and concentration c:

```text
dc/dt = λ(c_E − c_I) + G/V
```

The equation applies to CO₂ with coherent units and to vapour as mass/volume.
Without λ, G, or V it cannot predict an exact time. Indoor CO₂ at 1000 ppm is
an initial ventilation indicator, not an absolute health limit or complete IAQ
metric: [ASHRAE explains](https://www.ashrae.org/file%20library/about/position%20documents/pd-on-indoor-carbon-dioxide-english.pdf)
that CO₂ is not a global air-quality indicator and that sensor performance,
location, and calibration matter.

## Initial thresholds and air-quality sources

These values are conservative starting points, not medical values or mandatory
rules. Every implementation trace records value, unit, source, averaging window,
and version.

> [!WARNING]
> A number without its **unit**, **source**, and **averaging window** is not a
> health threshold and must not be presented as one.

| Type | Initial | Configurable range | Use |
|---|---|---|---|
| Personal comfort | target 22 °C, band ±1 °C, RH 40–60% | target 18–26 °C, band 0.5–3 °C, RH 30–70% | preference, never block |
| Technical benefit | ≥1 comfort point or favourable ΔAH ≥1 g/m³ | 0.5–3; 0.5–3 g/m³ | avoids marginal advice |
| Technical CO₂ | 1000 ppm; trend +150 ppm/h | 800–1500; 50–500 ppm/h | signal, not health threshold |
| Wind/gust | 35/50 km/h | 15–60 / 25–80 km/h | opening block |
| Rain | present; imminent probability 60% | 0–100% | block/penalty |
| Pollen | personal threshold | by species/user | ignore=I, reduce=P, avoid=B |
| Health/IAQ | no single threshold | source+unit+average required | policy, never diagnosis |

WHO 2021 keeps pollutant and averaging time distinct:

| Pollutant | WHO AQG level | Averaging time |
|---|---:|---|
| PM2.5 | 5 µg/m³; 15 µg/m³ | annual; 24 h |
| PM10 | 15 µg/m³; 45 µg/m³ | annual; 24 h |
| O₃ | 60 µg/m³; 100 µg/m³ | peak season; daily maximum 8 h |
| NO₂ | 10 µg/m³; 25 µg/m³ | annual; 24 h |
| SO₂ | 40 µg/m³ | 24 h |
| CO | 4 mg/m³ | 24 h |

These are exposure health guidelines, not automatic triggers. Details, including
short-window percentiles, are in the [WHO 2021 global guidelines](https://www.who.int/publications/i/item/9789240034228).
Every future health threshold includes source, unit, averaging time, and usage
warning. AQI always includes its standard and averaging period.

The initial free seasonal-European pollen source is **Open-Meteo Air Quality
API**, based on CAMS. It is a model forecast, not a window measurement. In
Europe CAMS is about 11 km, hourly, updated every 24 hours, and offers four
forecast days. Alder, birch, grass, mugwort, olive, and ragweed are available
only in Europe during pollen season, for up to four days; current conditions
use a 15-minute model [Open-Meteo](https://open-meteo.com/en/docs/air-quality-api).
UI and explanations attribute Open-Meteo/CAMS and show coverage, season,
resolution, and timestamp. No US provider is in scope.

> [!NOTE]
> Open-Meteo/CAMS is forecast-model data. Its spatial resolution and timestamp
> must remain visible whenever it contributes to pollen or outdoor-air advice.

## Scoring, result, and explanation

After blocks:

```text
S(action) = thermal benefit + vapour benefit + IAQ benefit
            − pollution penalty − uncertainty penalty − operational penalty
```

Operational penalty excludes quiet hours, cooldown, and contacts: they are
post-decision. Open requires score above threshold and durable benefit;
ventilate requires net but targeted/transient benefit; close requires
significantly worse outdoor conditions or a block. A configurable margin over
the next action is required; otherwise none.

The minimum result contains core/delivered action, proposed duration for
ventilate only, score per action, confidence, timestamp, used/discarded inputs
and ages, blocks, penalties, preferences, model, and guardrails. Trace IDs are
stable and ordered. A suppression always says both truth (“core: ventilate”)
and cause (“quiet hours”).

> [!TIP]
> A useful explanation always answers three questions in order: **what is the
> advice**, **which higher-priority fact decided it**, and **which helpful
> signal was considered but could not win**.

## Normative examples

| Scenario | Input | Expected result |
|---|---|---|
| Hot room, cool outside | I 28 °C/50%, E 20 °C/45%, valid weather | open: thermal benefit |
| Humid room | I 22 °C/70%, E 21 °C/45%, ΔAH<0 | ventilate: removes moisture |
| High CO₂ | 1400 ppm, +250 ppm/h, safe E | ventilate: air-renewal signal |
| Rain | current rain, known open window | close: weather block |
| Thunderstorm | current/imminent storm or lightning | close if open; never open |
| Wind | 55 km/h gust, threshold 50 | block; close if open |
| High PM2.5 | E above policy with valid average | block/penalty; comfort cannot win |
| Pollen ignore/reduce/avoid | high sensitive species | information / reduced duration / opening block |
| Critical data absent | stale wind or weather | never open/ventilate |
| Conflict | high CO₂ plus thunderstorm | weather wins; excluded benefit explained |

## Future test matrix

Every test verifies core/delivered action, score/confidence, ordered trace, and
absence of invented data.

| Area | Unit | Integration | Docker Lab |
|---|---|---|---|
| Blocks | each block alone and with CO₂/comfort; fail closed | entity/alert mapping | weather, rain, wind, contacts |
| Pollutants/pollen | every I/E pollutant, unit/average, three profiles | provider and attribution | PM, smoke, seasonal species |
| Physics | Magnus, HI, RC/mass limits and invalid data | conversion/timestamps | T/RH/CO₂ charts |
| Forecast | 15/30/60/120 min; absent/default/local calibration | refresh/errors | short opportunity |
| Precedence | conflicts, margin, stability | guardrails preserve core | cooldown, quiet hours, contacts |
| Explanation | deterministic trace per result | serialization/translations | readable advice/suppression |

Every future threshold, source, or rule extends this matrix with the narrowest
applicable regression test.

