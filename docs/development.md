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
python -m pytest tests/test_scoring_model.py tests/test_runtime.py tests/test_local_docker_runner.py -q
coverage run -m pytest
coverage report
```

The unit suite runs without Home Assistant. Install `requirements-ci.txt` to
run the Home Assistant integration suite locally on Linux; CI runs it on every
change using the version pinned there. Use `python scripts/ha-local-docker-test.py`
when you need to inspect the packaged integration in a local Home Assistant environment.

## Repository Layout

- `custom_components/ventwise/ventwise_core/` for the reusable scoring core
- `custom_components/ventwise/` for the Home Assistant integration layer
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
