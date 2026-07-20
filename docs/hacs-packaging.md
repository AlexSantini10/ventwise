# HACS Packaging

## Goal

Package the project so it can be installed from HACS as a Home Assistant
custom integration.

## Required Pieces

- Python package code
- Home Assistant integration folder under `custom_components/`
- metadata describing the integration
- documentation for installation and configuration
- a versioning strategy for releases

## Suggested Repository Shape

- `custom_components/temperature_comfort_recommender/`
- `src/`
- `tests/`
- `examples/`
- `docs/`

## Release Principles

- Keep the core reusable and versioned.
- Keep the integration stable before publishing.
- Add clear install steps for HACS users.
- Avoid requiring manual YAML edits for standard setup.

## Publication Notes

- The repository should be ready to add as a HACS custom repository.
- The integration should have clear metadata and a stable slug.
- The final public name should remain readable and user-friendly.

