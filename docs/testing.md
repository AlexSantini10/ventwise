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

- pure Python unit tests for scoring
- integration tests for configuration handling
- Home Assistant behavior tests for entity updates, if needed later
- regression tests for room management and config validation
- coverage checks on the reusable core and the HA runtime helpers

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
pytest
coverage run -m pytest
coverage report
```

## Local Home Assistant Sandbox

Use the local Docker sandbox to test the integration without reinstalling from
HACS on every run.

```powershell
python ha-local-docker-test.py
```

The script keeps Home Assistant runtime data outside the repository under
`%LOCALAPPDATA%\VentWise-HA-Test` and bind-mounts
`custom_components\ventwise` read-only into the container. The repo tree stays
clean for commits.

## Expectations

- keep the reusable core fully testable without Home Assistant
- add a focused regression test for every new scoring rule
- prefer parametrized tests for scenario matrices
- keep runtime helper tests small and deterministic
