# Testing

## Source of Truth

The test suite is the main safety net for the project. It should evolve with
the core engine and the Home Assistant runtime layer.

## What Must Be Verified

### Functional behavior

- open recommendation when outside is clearly more comfortable
- close recommendation when inside is already better
- no recommendation when the advantage is marginal
- room management keeps the saved configuration consistent
- config flow rejects invalid entity domains and out-of-range values

### Seasonal behavior

- summer scenario with outside cooler
- summer scenario with outside warm but still better perceived
- winter scenario with outside warmer and more comfortable
- winter scenario with no real benefit

### Noise control

- notifications do not repeat too often
- cooldown works
- quiet hours block notifications correctly
- short-lived spikes do not trigger alerts
- persisted runtime markers survive a restart

## Test Types

- `tests/unit/`: pure scoring, runtime parsing, sensor aggregation, package, and runner tests
- `tests/integration/`: configuration, entities, coordinator, notifications, translations, and Home Assistant framework tests
- `tests/system/`: end-to-end user journeys from submitted setup data to advice

Every user-visible behavior change needs a focused regression in the narrowest
layer that proves it; use integration or system tests when Home Assistant state
delivery or the full configuration journey matters.

## Supported Home Assistant Version

VentWise currently tests the latest stable Home Assistant release only.

The Home Assistant job uses Python 3.14.2 so the selected release can be
installed in CI.

## Recommended Test Matrix

- inside hotter, outside cooler
- inside cooler, outside hotter
- inside more humid, outside drier
- windy cold outside with warm inside
- neutral conditions near the target
- multi-room evaluation with rooms treated independently
- quiet hours and cooldown gate the recommendation
- persisted state is reloaded after restart
- debug attributes expose summary and per-room details

## Local Workflow

```bash
python -m pytest tests/unit -q
coverage run -m pytest
coverage report
```

CI has two required gates: **unit tests** and **Home Assistant integration
tests**. The latter use the same pinned Home Assistant version as release CI
and create HA entity states in memory, so they require no physical sensors.
On Windows, run the lightweight command above; the Home Assistant pytest
framework is exercised by the Linux CI runner.

## Local Home Assistant Sandbox

Use the local Docker Lab to test the integration manually without physical
hardware. It is completely isolated from any existing Home Assistant instance.

```powershell
python scripts/ha-local-docker-test.py
```

Every `up` or `restart` builds `ventwise-lab.zip` from the current checkout,
installs that package into the Lab profile, and starts Home Assistant. The
profile is persistent; reset it explicitly when a clean onboarding state is
needed:

```powershell
python scripts/ha-local-docker-test.py restart
python scripts/ha-local-docker-test.py reset
```

The script keeps all runtime data and the generated ZIP outside the repository
under `%LOCALAPPDATA%\VentWise-HA-Test`. It does not bind-mount integration
sources, use HACS, or inspect another HA profile.

The Lab verifies that the installed package version equals the generated ZIP
version before it reports success. A mismatch stops the command before manual
testing can use stale code.

The sandbox automatically provisions adjustable test fixtures:

- `input_number.ventwise_test_bedroom_temperature` and `_humidity`
- bedroom and living-room CO₂ helpers
- `input_number.ventwise_test_living_room_temperature` and `_humidity`
- `input_number.ventwise_test_outdoor_temperature`, `_humidity`, and `_wind_speed`
- `input_select.ventwise_test_weather_condition` (`sunny`, `rainy`, or `thunderstorm`)
- `weather.ventwise_test_weather`, which reads the outdoor helpers
- one living-room and two bedroom window contacts, represented by adjustable
  `input_boolean` helpers and derived `binary_sensor` entities

VentWise is configured automatically on the first Lab startup with a two-room
test entry. Change the helpers from the **VentWise Test Lab** sidebar dashboard
to create repeatable open, close, humidity, CO₂, wind, and multiple-window
scenarios. The dashboard displays the resulting recommendation, score, reason,
active flag, and aggregate window state for each room.

`tests/system/test_user_journey.py` covers the automated path from the submitted setup
data through room sensor readings, scoring, and the Italian explanation shown to
the user. It runs in the Home Assistant CI job.

## Expectations

- keep the reusable core fully testable without Home Assistant
- add a focused regression test for every new scoring rule
- prefer parametrized tests for scenario matrices
- keep runtime helper tests small and deterministic
- use `docs/project-rules.md` as the pre-merge checklist for quality gates and
  product rules
