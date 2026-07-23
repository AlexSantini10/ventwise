# Development Workflow

## Goal

Keep the repository easy to work on, test, and package without making the Home
Assistant integration depend on the development setup.

## Local Setup

- install Python 3.11 or newer
- create a virtual environment
- install the project in editable mode

```bash
python -m pip install -e .[dev]
```

## Common Commands

```bash
pytest
coverage run -m pytest
coverage report
```

## Repository Layout

- `src/` for the reusable scoring core
- `custom_components/ventwise/` for the Home Assistant integration
- `tests/` for unit and runtime coverage
- `docs/` for architecture and packaging notes

## CI / Release

- pushes to `main` run unit tests, HACS validation, Hassfest, and package build
- pushes to `test` branches run the same checks and can publish prerelease artifacts
- tag pushes matching `v*` rerun validation, build the package, and create the GitHub Release
- release checks reuse the same packaging script as CI

## Working Rules

- keep the reusable core independent from Home Assistant APIs
- keep user-facing configuration in the integration UI
- keep release and packaging concerns documented here rather than in ad hoc notes
- keep the backlog in GitHub issues

## Versioning

- The integration release version is driven by `custom_components/ventwise/manifest.json`.
- To create a new release, update the manifest version and let the release workflow publish from that value.
- the core package should remain versioned through `pyproject.toml`
- HACS publication continues to use the integration manifest version
  - experimental builds use prerelease tags derived from the manifest version and a zero-padded numeric `b` suffix
- release automation is handled by GitHub Actions
