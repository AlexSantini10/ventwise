# Development Workflow

## Goal

Keep the repository easy to work on, test, and package without making the Home
Assistant integration depend on the development setup.

## Local Setup

Install Python 3.11 or newer and Git. From a clone of the repository, create a
virtual environment and install the development dependencies.

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Common Commands

```bash
python -m pytest tests/unit -q
coverage run -m pytest
coverage report
```

The unit suite runs without Home Assistant. To execute the exact Python and
Home Assistant test gates used by CI from any host with Docker Desktop, run:

```powershell
.\scripts\test-ci-docker.ps1
```

To enforce the same check automatically before every commit and push, enable
the repository hooks once after cloning:

```powershell
git config core.hooksPath .githooks
```

The hooks use the cached Docker image and clean up the disposable container and
Compose network when they finish. A failed test blocks the commit or push.

The command builds a cached Python 3.14.2 image, mounts the checkout
read-only, and runs `tests/unit`, `tests/integration`, and `tests/system` in a
disposable container. Pass pytest paths or flags to narrow a run:

```powershell
.\scripts\test-ci-docker.ps1 tests/integration tests/system -q
```

It is independent of the [Docker Test Lab](docker-test-lab.md), which remains
the packaged local Home Assistant environment for manual testing without
physical hardware.

## Repository Layout

- `custom_components/ventwise/ventwise_core/` for the reusable scoring core
- `custom_components/ventwise/application/` for runtime coordination, state, and notifications
- `custom_components/ventwise/configuration/` for shared config and options-flow logic
- `custom_components/ventwise/entities/` for shared entity behavior
- `custom_components/ventwise/` root for Home Assistant discovery entry points and platforms
- `tests/unit/`, `tests/integration/`, and `tests/system/` for focused test layers
- `docs/` for architecture and packaging notes

Keep only Home Assistant discovery entry points and platform modules at the
integration root. All implementation imports should target the internal module
that owns the behavior.

## CI / Release

- pushes to `main` run unit tests, HACS validation, Hassfest, and package build
- pushes to `test` branches run the same checks and can publish prerelease artifacts
- tag pushes matching `v*` rerun validation, build the package, and create the GitHub Release
- release checks reuse the same packaging script as CI

## Working Rules

- keep the reusable core independent from Home Assistant APIs
- keep user-facing configuration in the integration UI
- keep the project rules documented in `docs/project-rules.md`
- keep release and packaging concerns documented here rather than in ad hoc notes
- keep the backlog in GitHub issues

## Versioning

- The integration release version is driven by `custom_components/ventwise/manifest.json`.
- To create a new release, update the manifest version and let the release workflow publish from that value.
- the core package should remain versioned through `pyproject.toml`
- HACS publication continues to use the integration manifest version
  - experimental builds use prerelease tags derived from the manifest version and a zero-padded numeric `b` suffix
- release automation is handled by GitHub Actions
