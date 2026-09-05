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
- a clean development workflow and repeatable test setup
- GitHub Actions for HACS validation, Hassfest, and release packaging

## Suggested Repository Shape

- `custom_components/ventwise/`
- `custom_components/ventwise/ventwise_core/`
- `tests/`
- `docs/`

## Release Principles

- Keep the core reusable and versioned.
- Keep the integration stable before publishing.
- Add clear install steps for HACS users.
- Avoid requiring manual YAML edits for standard setup.
- Publish stable releases from `main` only.
- Publish experimental prereleases from the `test` branch family with a zero-padded `vX.Y.Zb000000N`-style tag.
- Keep prereleases marked as GitHub prereleases so HACS can hide them unless the prerelease switch is enabled.

## Publication Notes

- The repository should be ready to add as a HACS custom repository.
- The integration should have clear metadata and a stable slug.
- The final public name should remain readable and user-friendly.
- the repository root should stay clean and reproducible for releases
- release artifacts should be produced automatically for installation in Home Assistant

For user-facing installation, update, and removal instructions, see the
[user guide](user-guide.md). This document is for maintainers and release work.

## Discoverability

HACS searches the GitHub repository name, description, author, type, status,
and topics. It does not index the README for its own search results. Keep the
GitHub description short and user-focused:

> Weather-aware window ventilation and indoor-comfort recommendations for Home
> Assistant.

Use accurate GitHub topics for the ways people search for VentWise, including
`window`, `windows`, `window-ventilation`, `ventilation`, `weather`,
`weather-forecast`, `indoor-comfort`, `temperature`, `humidity`, and
`recommendations`. The existing Home Assistant and HACS topics remain part of
that set. Do not add topics for capabilities that are not implemented, such as
air-quality recommendations or automatic window control.

The README can use the same natural-language terms to help GitHub and web
search, but it does not affect HACS in-app search.

VentWise remains installable as a custom repository through its My Home
Assistant link. To make it discoverable among HACS's available repositories,
submit it to `hacs/default` only when the project is ready for public listing:

- complete the required Home Assistant brand assets;
- publish a stable GitHub release after the CI checks pass; and
- meet the current HACS publisher requirements before opening the external PR.
