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
- `custom_components/temperature_comfort_recommender/` for the Home Assistant integration
- `tests/` for unit and runtime coverage
- `docs/` for architecture and packaging notes

## Working Rules

- keep the reusable core independent from Home Assistant APIs
- keep user-facing configuration in the integration UI
- keep release and packaging concerns documented here rather than in ad hoc notes
- keep the backlog in GitHub issues

## Versioning

- the core package should remain versioned through `pyproject.toml`
- HACS publication continues to use the integration manifest version
- release automation will be handled in a later task
