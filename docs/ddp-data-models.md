# DDP Data, Physical Models, and Objective Function

This document defines the canonical data model, physical approximations, and
proposed constrained objective for the target Deterministic Decision Pipeline.
Thresholds are software configuration proposals, not universal health limits.

## Scope and notation

The DDP treats temperature, humidity, and CO2 as separate environmental
objectives. Relative humidity is used for comfort; humidity ratio is used for
air-exchange calculations; absolute humidity is available for display.

Let `a` be a candidate action, `b` the baseline that maintains the current
state, `H` the common horizon (initially 30 minutes), `x_a(t)` the estimated
state under `a`, `I` the configured factors, `w_i` their weights, `c_k` normalized
penalties, and `lambda_k` non-negative penalty coefficients.

## Data inventory

| Scope | Data | Purpose | Requirement |
| --- | --- | --- | --- |
| Room | Indoor temperature and timestamp | Thermal state | Base |
| Room | Indoor RH and timestamp | Comfort and humidity ratio | Base for humidity |
| Room | Indoor CO2 and trend | IAQ | Optional/configurable |
| Room | Window contacts | Candidate state and confirmation | Strongly recommended |
| Room | Volume, opening area, exposure | Future air-exchange calibration | Optional advanced |
| Room | Occupancy, HVAC, surface temperature | Future source and condensation estimates | Optional/future |
| Outdoor | Temperature, RH, timestamp, quality | Thermal and humidity effects | Base |
| Outdoor | Pressure | Humidity-ratio calculation | Optional, documented estimate allowed |
| Outdoor | Wind, gusts, condition, precipitation | Safety policy | Required when policy uses it |
| Outdoor | PM, pollen, species, and source | Outdoor-air-quality policy | Required for `BLOCK` policy |
| Forecast | Time series with valid times | Candidate safety filtering | When available |
| Configuration | Comfort bands, thresholds, policies, weights, horizon, durations | Decision policy | Required |
| Context | Current time, decision memory, quiet hours, cooldown | Stabilization | Required |

Short-term forecasts detect deterioration during the candidate duration plus a
buffer; they do not automatically extend the objective horizon. Provider-
specific pollen scales remain typed and are not converted into one index.
Absence is not zero.

## Canonical units and provenance

| Dimension | Accepted inputs | Canonical representation |
| --- | --- | --- |
| Temperature | Celsius, Fahrenheit, Kelvin | Celsius |
| Relative humidity | Percentage, explicitly declared fraction | Percentage RH |
| Absolute humidity | g/m3, mg/m3 | g/m3 |
| Humidity ratio | g/kg dry air, kg/kg | g/kg dry air |
| CO2 | ppm; mg/m3 only with known temperature and pressure | ppm |
| Wind and gusts | m/s, km/h, mph, knots | m/s |
| Pressure | Pa, hPa, bar, kPa, inHg | hPa |
| Particulate matter | micrograms/m3, mg/m3 | micrograms/m3 |
| Precipitation | mm, inches, corresponding rates | mm and mm/h |
| Probability | Percentage, explicitly declared fraction | [0, 1] |
| Pollen | grains/m3 or provider-specific index | Typed source unit |

Every normalized value includes source, observed or valid time, original unit,
quality, and provenance. Conversion is rejected when the dimension or unit is
ambiguous.

For CO2 supplied in mg/m3, the ideal-gas conversion is:

$$
C_{ppm}=C_{mg/m^3}\frac{1000RT_K}{p_{Pa}M_{CO2}}
$$

where `M_CO2 = 44.01 g/mol` and `R = 8.314 J/(mol K)`. A constant conversion
independent of temperature and pressure is not valid.

## Psychrometric relationships

For typical indoor temperatures, the Magnus approximation gives saturation
vapor pressure in hPa:

$$
e_s(T)=6.112\exp\left(\frac{17.62T}{243.12+T}\right)
$$

$$
e(T,RH)=\frac{RH}{100}e_s(T)
$$

Absolute humidity is:

$$
AH(T,RH)=216.7\frac{e(T,RH)}{T+273.15}\quad [g/m^3]
$$

Humidity ratio is:

$$
W(T,RH,p)=621.98\frac{e(T,RH)}{p-e(T,RH)}\quad [g/kg_{dry\ air}]
$$

Pressure and vapor pressure must use the same unit, with `p > e`. A documented
pressure estimate may be used with reduced confidence, but it must not be
represented as measured pressure.

After estimating future temperature and humidity ratio, reconstruct RH:

$$
RH(T,W,p)=100\frac{pW/(621.98+W)}{e_s(T)}
$$

Values above 100% indicate saturation, condensation risk, or model limits and
must not be silently clipped. Exchange decisions use `W`, not a direct RH
comparison. Cold outdoor air can have higher RH but less water content than
warm indoor air.

## Dynamic impact models

An ideal mixed-air CO2 model is:

$$
\frac{dC}{dt}=-\lambda(C-C_{out})+g_C
$$

and, for constant parameters:

$$
C(t)=C_{out}+(C_0-C_{out})e^{-\lambda t}+\frac{g_C}{\lambda}(1-e^{-\lambda t})
$$

For `lambda = 0`, use the limiting form `C(t) = C0 + gC t`. Without a valid
source estimate, `gC = 0` is a declared simplification, not a claim about
reality. The equivalent exchange fraction `1 - exp(-lambda*t)` is not a
guaranteed percentage of air replaced in a real room.

Humidity can use the analogous model:

$$
\frac{dW}{dt}=-\lambda(W-W_{out})+g_W
$$

with future RH reconstructed from future `T` and `W`. Showers, cooking,
humidifiers, materials, and ventilation systems can invalidate the source
assumptions.

A simple effective temperature model is:

$$
\frac{dT}{dt}=k_T(T_{out}-T)+q_T(t)
$$

`kT` is an effective thermal coefficient and must not automatically be equated
with air-exchange rate. HVAC, solar radiation, thermal mass, and the envelope
are separate effects.

The MVP estimator returns normalized directional effects and confidence. A
calibrated estimator may return trajectories when local parameters are
identifiable, with assumptions and a fallback to the heuristic model.

## Normalized discomfort and costs

For an interval `[L, U]`, define:

$$
\delta(z;L,U)=\max(0,L-z,z-U)
$$

Example bounded quadratic functions are:

$$
d_T(T)=\min\left(1,\left[\frac{\delta(T;T_-,T_+)}{s_T}\right]^2\right)
$$

$$
d_H(RH)=\min\left(1,\left[\frac{\delta(RH;RH_-,RH_+)}{s_H}\right]^2\right)
$$

CO2 is one-sided and configurable:

$$
d_C(C)=\min\left(1,\left[\frac{\max(0,C-C_{low})}{C_{high}-C_{low}}\right]^2\right)
$$

with `C_high > C_low`. Example values are software parameters, not health
limits. If CO2 is disabled, remove its dimension and use a coherent weight
profile. If enabled but missing or stale, it is unknown, not zero discomfort.

Normalize configured weights over enabled factors:

$$
\bar w_i=\frac{w_i}{\sum_{j\in I}w_j},\qquad w_i\geq0
$$

Do not silently renormalize because a configured sensor is temporarily missing;
handle quality explicitly or apply a documented conservative fallback.

The instantaneous environmental cost is:

$$
J(x(t))=\sum_{i\in I}\bar w_i d_i(x(t))
$$

Additional penalties may represent estimated energy, reduced outdoor quality,
repeated intervention, inconvenience, or forecast deterioration. They must be
dimensionless, separately defined, and must not duplicate discomfort. Hard
blocks exclude candidates; they are not large costs.

## Proposed constrained net-benefit function

Let `A_safe(s)` be candidates allowed by the current state and safety policy:

$$
B(a)=
\begin{cases}
-\infty, & a\notin A_{safe}(s)\\[3pt]
\frac{1}{H}\int_0^H[J(x_b(t))-J(x_a(t))]dt-\sum_{k\in K}\lambda_kc_k(a), & a\in A_{safe}(s)
\end{cases}
$$

Positive `B` means lower expected average discomfort than the baseline. The
result is dimensionless and must not be displayed as a health, comfort, or
energy-saving percentage.

For heuristic estimation, replace the integral with a shared normalized
estimate:

$$
B_{heur}(a)=\sum_{i\in I}\bar w_i\hat b_i(a)-\sum_{k\in K}\lambda_kc_k(a)
$$

where each `bhat_i` is benefit relative to the baseline, not current severity.

Select the maximum admissible candidate with deterministic tie-breaking that
prefers lower intervention and shorter duration. Activate it only when:

$$
B(a_{best})>\tau\quad\land\quad quality(a_{best})\geq q_{min}
$$

Stability is a separate gate. A critical close guardrail takes precedence over
ordinary gates. Confidence cannot be converted into a comfort cost that a high
score can overcome.

## Initial parameters and validation

Initial calibration proposals include a 21 C target with configurable +/-1 C,
RH 40-60%, 5/10/20/30-minute candidates, a 30-minute horizon, and a notification
cooldown around 15 minutes. These are engineering starting points.

Tests must cover dimensional equivalence, invalid units, psychrometric domains,
monotonicity, baseline benefit of zero, common-horizon comparison, hard-block
precedence, missing-data handling, confidence gates, and double-counting.
